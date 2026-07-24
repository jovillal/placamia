from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import (
    PaymentEventSource,
    PaymentLifecycleError,
    PaymentStatus,
    PaymentTransitionTrigger,
    TERMINAL_PAYMENT_STATUSES,
    transition_payment_status,
)
from app.domain.payment_provider_gateway import CheckoutRequest, CheckoutSession
from app.domain.provider_adapter import ProviderAdapter
from app.models.order import Order
from app.models.order_item import OrderItem, OrderItemType
from app.models.payment import Payment
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import (
    LEGACY_GENERIC_PROVIDER_CODE,
    PaymentRepository,
)
from app.services.payment_provider_registry import (
    PaymentProviderConfigurationError,
    PaymentProviderRuntime,
    PaymentProviderRuntimeFactory,
    UnsupportedPaymentProvider,
    WOMPI_PROVIDER_CODE,
)
from app.services.pricing_service import (
    PathAPricingRequest,
    PathAPricingService,
    PricingItemType,
    PricingRejected,
)
from app.services.wompi_payment_provider import (
    InvalidPaymentAmount,
    PaymentProviderHandoffError,
    UnsupportedPaymentCurrency,
)

NON_TERMINAL_PAYMENT_STATUSES = frozenset(
    status for status in PaymentStatus if status not in TERMINAL_PAYMENT_STATUSES
)
ZERO_MONEY = Decimal("0.00")


@dataclass(frozen=True)
class PaymentInitializationResult:
    """Result of creating or reusing a hosted payment checkout."""

    order: Order
    payment: Payment
    checkout_session: CheckoutSession
    created: bool


@dataclass(frozen=True)
class PaymentInitializationRejected(ValueError):
    """Raised when payment initialization rejects a request."""

    code: str
    message: str

    def __str__(self) -> str:
        """Return the customer-safe rejection message."""
        return self.message


class PaymentInitializationService:
    """Initialize Wompi checkout handoffs from backend-owned Payment state."""

    def __init__(
        self,
        order_repository: OrderRepository,
        payment_repository: PaymentRepository,
        provider_adapter: ProviderAdapter,
        payment_provider_runtime_factory: PaymentProviderRuntimeFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Store persistence, pricing, provider, configuration, and clock ports.

        Args:
            order_repository: Owner-scoped Order persistence boundary.
            payment_repository: Payment persistence boundary.
            provider_adapter: Fulfillment-provider catalog adapter used only
                for current checkout eligibility and pricing validation.
            payment_provider_runtime_factory: Lazy payment-provider registry
                and configuration factory.
            clock: Injectable UTC clock used for deterministic expiration.

        Side effects:
            None.
        """
        self.order_repository = order_repository
        self.payment_repository = payment_repository
        self.pricing_service = PathAPricingService(provider_adapter)
        self.payment_provider_runtime_factory = payment_provider_runtime_factory
        self.clock = clock or (lambda: datetime.now(UTC))

    async def initialize_payment(
        self,
        *,
        order_id: int,
        current_user: User,
    ) -> PaymentInitializationResult:
        """Create or reuse one authenticated customer's Wompi checkout.

        Args:
            order_id: Backend Order identifier from the strict request body.
            current_user: Authenticated user resolved from request context.

        Returns:
            New or reused Payment plus its normalized redirect handoff.

        Raises:
            PaymentInitializationRejected: If ownership, eligibility, lifecycle,
                provider routing, configuration, or handoff construction fails.

        Side effects:
            Acquires the owner-scoped Order row lock, may expire one stale
            restartable Payment, and may stage one new `requires_action`
            Payment. The caller owns transaction commit or rollback.
        """
        order = self.order_repository.get_order_for_customer_for_update(
            order_id,
            current_user.id,
        )
        if order is None:
            raise PaymentInitializationRejected(
                code="order_not_found",
                message="Order was not found for the authenticated user.",
            )

        self._validate_payable_order(order)
        payments = self.payment_repository.get_payments_for_order(order.id)
        payment_statuses = [
            (payment, self._payment_status(payment)) for payment in payments
        ]
        if any(
            payment_status is PaymentStatus.VERIFIED
            for _payment, payment_status in payment_statuses
        ):
            raise PaymentInitializationRejected(
                code="order_not_payable",
                message="Order already has a verified Payment.",
            )

        active_payments = [
            (payment, payment_status)
            for payment, payment_status in payment_statuses
            if payment_status in NON_TERMINAL_PAYMENT_STATUSES
        ]
        if len(active_payments) > 1:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            )
        if active_payments:
            payment, payment_status = active_payments[0]
            return await self._handle_active_payment(
                order=order,
                payment=payment,
                payment_status=payment_status,
                current_user=current_user,
            )

        return await self._create_wompi_payment(
            order=order,
            current_user=current_user,
        )

    async def _handle_active_payment(
        self,
        *,
        order: Order,
        payment: Payment,
        payment_status: PaymentStatus,
        current_user: User,
    ) -> PaymentInitializationResult:
        """Apply the exact existing-Payment provider and status matrix."""
        if payment.provider_code == LEGACY_GENERIC_PROVIDER_CODE:
            raise PaymentInitializationRejected(
                code="payment_provider_not_routable",
                message="Existing Payment cannot be routed to a provider.",
            )
        if payment.provider_code != WOMPI_PROVIDER_CODE:
            raise PaymentInitializationRejected(
                code="payment_provider_not_routable",
                message="Existing Payment cannot be routed to a provider.",
            )
        if not payment.merchant_reference or payment.checkout_expires_at is None:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            )
        if payment_status is PaymentStatus.PENDING:
            raise PaymentInitializationRejected(
                code="payment_in_progress",
                message="Payment processing is already in progress.",
            )

        now = _normalize_utc(self.clock())
        checkout_expires_at = _normalize_utc(payment.checkout_expires_at)
        if payment_status is PaymentStatus.INITIATED and checkout_expires_at > now:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            )
        if checkout_expires_at <= now:
            self._expire_restartable_payment(payment, payment_status)
            return await self._create_wompi_payment(
                order=order,
                current_user=current_user,
            )
        if payment_status is not PaymentStatus.REQUIRES_ACTION:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            )

        runtime = self._provider_runtime()
        checkout_session = await self._initialize_checkout(
            runtime=runtime,
            provider_code=payment.provider_code,
            payment=payment,
            current_user=current_user,
        )
        return PaymentInitializationResult(
            order=order,
            payment=payment,
            checkout_session=checkout_session,
            created=False,
        )

    async def _create_wompi_payment(
        self,
        *,
        order: Order,
        current_user: User,
    ) -> PaymentInitializationResult:
        """Construct a handoff before staging one final Wompi Payment row."""
        runtime = self._provider_runtime()
        try:
            provider_code, _provider = runtime.registry.get_default()
        except UnsupportedPaymentProvider as exc:
            raise _provider_unavailable() from exc
        if provider_code != WOMPI_PROVIDER_CODE:
            raise _provider_unavailable()

        payment_id = self.payment_repository.allocate_payment_id()
        now = _normalize_utc(self.clock())
        checkout_expires_at = _truncate_to_milliseconds(
            now + timedelta(seconds=runtime.checkout_ttl_seconds)
        )
        payment = Payment(
            id=payment_id,
            order_id=order.id,
            provider_code=provider_code,
            merchant_reference=f"placamia-payment-{payment_id}",
            status=PaymentStatus.REQUIRES_ACTION.value,
            amount=order.total_amount,
            currency=order.currency,
            checkout_expires_at=checkout_expires_at,
        )
        checkout_session = await self._initialize_checkout(
            runtime=runtime,
            provider_code=provider_code,
            payment=payment,
            current_user=current_user,
        )
        payment.provider_checkout_reference = (
            checkout_session.provider_checkout_reference
        )
        self.payment_repository.create_payment(payment)
        return PaymentInitializationResult(
            order=order,
            payment=payment,
            checkout_session=checkout_session,
            created=True,
        )

    async def _initialize_checkout(
        self,
        *,
        runtime: PaymentProviderRuntime,
        provider_code: str,
        payment: Payment,
        current_user: User,
    ) -> CheckoutSession:
        """Resolve the persisted provider and return its normalized handoff."""
        try:
            provider = runtime.registry.get(provider_code)
            session = await provider.initialize_checkout(
                CheckoutRequest(
                    merchant_reference=payment.merchant_reference,
                    amount=payment.amount,
                    currency=payment.currency,
                    customer_email=current_user.email,
                    return_url=runtime.return_url,
                    expires_at=payment.checkout_expires_at,
                )
            )
        except UnsupportedPaymentCurrency as exc:
            raise PaymentInitializationRejected(
                code="unsupported_payment_currency",
                message="Payment currency is not supported.",
            ) from exc
        except InvalidPaymentAmount as exc:
            raise PaymentInitializationRejected(
                code="invalid_payment_amount",
                message="Payment amount is invalid.",
            ) from exc
        except (
            PaymentProviderConfigurationError,
            PaymentProviderHandoffError,
            UnsupportedPaymentProvider,
        ) as exc:
            raise _provider_unavailable() from exc
        except Exception as exc:
            raise _provider_unavailable() from exc

        if (
            session.merchant_reference != payment.merchant_reference
            or session.expires_at is None
            or payment.checkout_expires_at is None
            or _normalize_utc(session.expires_at)
            != _normalize_utc(payment.checkout_expires_at)
        ):
            raise _provider_unavailable()
        return session

    def _provider_runtime(self) -> PaymentProviderRuntime:
        """Build validated provider runtime with one redacted failure contract."""
        try:
            return self.payment_provider_runtime_factory.create()
        except Exception as exc:
            raise _provider_unavailable() from exc

    def _expire_restartable_payment(
        self,
        payment: Payment,
        payment_status: PaymentStatus,
    ) -> None:
        """Expire a stale initiated/requires-action checkout before replacement."""
        try:
            transition = transition_payment_status(
                payment_status,
                PaymentStatus.EXPIRED,
                PaymentTransitionTrigger.CHECKOUT_WINDOW_ELAPSED,
                event_source=PaymentEventSource.PAYMENT_INITIALIZATION,
            )
        except PaymentLifecycleError as exc:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            ) from exc
        payment.status = transition.to_status.value
        self.payment_repository.update_payment(payment)

    def _validate_payable_order(self, order: Order) -> None:
        """Reject Orders that cannot start a payment handoff."""
        if order.status != OrderStatus.DRAFT.value:
            raise PaymentInitializationRejected(
                code="order_not_payable",
                message="Only draft orders can initialize payment.",
            )
        if order.payment_provider_reference is not None or order.payment_verified_at:
            raise PaymentInitializationRejected(
                code="order_not_payable",
                message="Orders with payment confirmation fields cannot initialize payment.",
            )
        if order.total_amount <= ZERO_MONEY:
            raise PaymentInitializationRejected(
                code="invalid_payment_amount",
                message="Payment amount is invalid.",
            )
        if not order.currency or order.currency != order.currency.upper():
            raise PaymentInitializationRejected(
                code="unsupported_payment_currency",
                message="Payment currency is not supported.",
            )
        self._validate_order_items(order)

    def _validate_order_items(self, order: Order) -> None:
        """Validate immutable item snapshots required for payment eligibility."""
        if not order.items:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order has no payable item snapshots.",
            )

        line_total = ZERO_MONEY
        for item in order.items:
            self._validate_order_item(order, item)
            line_total += item.line_total_amount
        if line_total != order.total_amount:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item totals do not match the backend order total.",
            )

    def _validate_order_item(self, order: Order, item: OrderItem) -> None:
        """Reject stale, unsupported, or non-provider-ready item snapshots."""
        if item.item_type != OrderItemType.PRODUCT or item.product_id is None:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Only product item snapshots can initialize payment.",
            )
        if item.product is None or not item.product.is_active:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item product is no longer active.",
            )
        self._validate_current_product_priceability(item)
        if item.quantity <= 0 or item.line_total_amount <= ZERO_MONEY:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item quantity and total must be positive.",
            )
        if item.currency != order.currency:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item currency must match the order currency.",
            )
        if not item.assigned_provider_id or not item.provider_pricing_reference:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item is missing provider-ready pricing data.",
            )
        if not isinstance(item.provider_payload_snapshot, dict):
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item is missing provider payload snapshot data.",
            )

    def _validate_current_product_priceability(self, item: OrderItem) -> None:
        """Reject items that no longer pass current Path A pricing rules."""
        try:
            validation = self.pricing_service.validate_pricing_request(
                PathAPricingRequest(
                    item_type=PricingItemType.PRODUCT,
                    item=item.product,
                    quantity=item.quantity,
                    options=item.selected_options,
                )
            )
        except PricingRejected as exc:
            raise PaymentInitializationRejected(
                code=exc.code,
                message=str(exc),
            ) from exc
        if validation.provider_quote_reference != item.provider_pricing_reference:
            raise PaymentInitializationRejected(
                code="order_items_not_payable",
                message="Order item provider pricing reference is stale.",
            )

    def _payment_status(self, payment: Payment) -> PaymentStatus:
        """Return canonical persisted status or reject unknown state."""
        try:
            return PaymentStatus(payment.status)
        except ValueError as exc:
            raise PaymentInitializationRejected(
                code="payment_state_invalid",
                message="Payment state cannot initialize checkout.",
            ) from exc


def _provider_unavailable() -> PaymentInitializationRejected:
    """Return the single redacted provider-configuration/handoff failure."""
    return PaymentInitializationRejected(
        code="payment_provider_unavailable",
        message="Payment provider is temporarily unavailable.",
    )


def _normalize_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, treating SQLite-naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _truncate_to_milliseconds(value: datetime) -> datetime:
    """Return one datetime truncated to canonical millisecond precision."""
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)
