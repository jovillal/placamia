from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus, TERMINAL_PAYMENT_STATUSES
from app.domain.provider_adapter import ProviderAdapter
from app.models.order import Order
from app.models.order_item import OrderItem, OrderItemType
from app.models.payment import Payment
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.pricing_service import (
    PathAPricingRequest,
    PathAPricingService,
    PricingItemType,
    PricingRejected,
)

NON_TERMINAL_PAYMENT_STATUSES = frozenset(
    status for status in PaymentStatus if status not in TERMINAL_PAYMENT_STATUSES
)
"""Payment statuses that represent an active reusable payment attempt."""

ZERO_MONEY = Decimal("0.00")


@dataclass(frozen=True)
class PaymentInitializationResult:
    """Result of initializing or reusing a backend-owned payment attempt.

    Attributes:
        order: The authenticated customer's payable draft Order.
        payment: The existing or newly persisted Payment attempt.
        created: Whether this call created a new Payment row.
    """

    order: Order
    payment: Payment
    created: bool


@dataclass(frozen=True)
class PaymentInitializationRejected(ValueError):
    """Raised when payment initialization rejects a request.

    Attributes:
        code: Stable rejection reason for API responses and tests.
        message: Human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


class PaymentInitializationService:
    """Initialize provider-neutral payment attempts for eligible draft Orders.

    The service loads the Order through backend-derived ownership, validates
    that the persisted draft Order and immutable item snapshots are still
    payment-eligible, reuses an existing non-terminal Payment attempt when one
    exists, or stages a new `initiated` Payment using backend-owned amount and
    currency values. It does not accept frontend payment claims, store card
    data, confirm Orders, or trigger provider handoff.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        payment_repository: PaymentRepository,
        provider_adapter: ProviderAdapter,
    ) -> None:
        """Store repositories used by payment initialization.

        Args:
            order_repository: Repository used to load authenticated Orders.
            payment_repository: Repository used to read or create Payments.
            provider_adapter: Backend-owned provider boundary used to
                revalidate current direct-checkout eligibility and priceability.
        """
        self.order_repository = order_repository
        self.payment_repository = payment_repository
        self.pricing_service = PathAPricingService(provider_adapter)

    def initialize_payment(
        self,
        *,
        order_id: int,
        current_user: User,
    ) -> PaymentInitializationResult:
        """Create or return a payment attempt for one authenticated draft Order.

        Args:
            order_id: Backend Order identifier from the request body.
            current_user: Authenticated user resolved from request context.

        Returns:
            PaymentInitializationResult containing the payable Order and
            existing or newly created Payment.

        Raises:
            PaymentInitializationRejected: If the Order is missing, not owned by
                the current user, not in a payable draft state, has stale or
                ineligible or currently non-priceable item snapshots, or has
                unsupported Payment state.

        Side effects:
            Stages one new Payment row in the current transaction when no active
            payment attempt exists. The caller remains responsible for commit or
            rollback.
        """
        order = self.order_repository.get_order_for_customer(
            order_id,
            current_user.id,
        )
        if order is None:
            raise PaymentInitializationRejected(
                code="order_not_found",
                message="Order was not found for the authenticated user.",
            )

        self._validate_payable_order(order)

        existing_payment = self._active_payment_for_order(order.id)
        if existing_payment is not None:
            return PaymentInitializationResult(
                order=order,
                payment=existing_payment,
                created=False,
            )

        payment = self.payment_repository.create_legacy_payment(
            Payment(
                order_id=order.id,
                status=PaymentStatus.INITIATED.value,
                amount=order.total_amount,
                currency=order.currency,
            )
        )
        return PaymentInitializationResult(order=order, payment=payment, created=True)

    def _active_payment_for_order(self, order_id: int) -> Payment | None:
        """Return the newest non-terminal Payment for an Order, if present."""
        for payment in self.payment_repository.get_payments_for_order(order_id):
            payment_status = self._payment_status(payment)
            if payment_status in NON_TERMINAL_PAYMENT_STATUSES:
                return payment
        return None

    def _validate_payable_order(self, order: Order) -> None:
        """Reject Orders that cannot start a payment attempt."""
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
                code="order_not_payable",
                message="Order total must be positive to initialize payment.",
            )

        if not order.currency or order.currency != order.currency.upper():
            raise PaymentInitializationRejected(
                code="order_not_payable",
                message="Order currency is not a supported canonical currency.",
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
        """Return the canonical PaymentStatus for a persisted Payment."""
        try:
            return PaymentStatus(payment.status)
        except ValueError as exc:
            raise PaymentInitializationRejected(
                code="unsupported_payment_status",
                message="Existing payment has an unsupported status.",
            ) from exc
