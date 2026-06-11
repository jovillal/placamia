from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.order_lifecycle import (
    OrderStatus,
    OrderStatusTransitionError,
    OrderTransitionTrigger,
    transition_order_status,
)
from app.domain.payment_lifecycle import (
    PaymentEventSource,
    PaymentLifecycleError,
    PaymentStatus,
    validate_order_confirmation_from_payment,
    validate_payment_confirmation_source,
)
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.payment_webhook_verification_service import TrustedPaymentWebhook


@dataclass(frozen=True)
class PaymentWebhookProcessingRejected(ValueError):
    """Raised when a verified payment webhook cannot confirm an order.

    Attributes:
        code: Stable rejection reason for routes and tests.
        message: Safe human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the safe human-readable rejection message."""
        return self.message


@dataclass(frozen=True)
class TrustedPaymentEvent:
    """Provider-neutral payment event extracted from a verified webhook.

    Attributes:
        event_id: Provider event identifier verified by the signature boundary.
        order_id: Backend order identifier referenced by the payment provider.
        payment_status: Provider-reported payment lifecycle status.
        payment_provider_reference: Provider payment reference to persist.
        amount: Provider-confirmed payment amount.
        currency: Provider-confirmed payment currency.
        customer_id: Optional backend customer id echoed by the provider.
    """

    event_id: str
    order_id: int
    payment_status: PaymentStatus
    payment_provider_reference: str
    amount: Decimal
    currency: str
    customer_id: int | None


@dataclass(frozen=True)
class PaymentWebhookProcessingResult:
    """Successful payment webhook processing result.

    Attributes:
        order: Persisted or idempotently matched Order.
        event: Trusted provider-neutral payment event.
    """

    order: Order
    event: TrustedPaymentEvent


class PaymentWebhookProcessingService:
    """Convert verified payment webhooks into confirmed backend orders.

    The service receives a webhook that has already passed signature
    verification, validates provider-neutral payment fields against persisted
    Order state, and persists only payment confirmation fields plus the
    `draft -> confirmed` order transition. It does not initialize payments,
    trust frontend claims, call provider handoff, or persist provider
    acceptance/rejection.
    """

    event_source = PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK

    def __init__(self, order_repository: OrderRepository) -> None:
        """Store repositories used for payment webhook processing.

        Args:
            order_repository: Repository used to read and update Orders.

        Side effects:
            None.
        """
        self.order_repository = order_repository

    def process_verified_webhook(
        self,
        trusted_webhook: TrustedPaymentWebhook,
    ) -> PaymentWebhookProcessingResult:
        """Confirm an eligible order from a verified provider webhook.

        Args:
            trusted_webhook: Provider-neutral webhook returned by the signature
                verification boundary.

        Returns:
            Payment webhook processing result with the updated or idempotently
            matched Order and trusted payment event.

        Raises:
            PaymentWebhookProcessingRejected: If payload shape, payment source,
                payment status, order identity, amount, currency, or order
                lifecycle validation rejects the confirmation.

        Side effects:
            On first valid confirmation, updates the Order status to
            `confirmed`, writes `payment_provider_reference`, and writes
            `payment_verified_at`. Idempotent same-reference replays do not
            mutate the Order. Provider handoff is never triggered here.
        """
        event = self._trusted_payment_event_from_webhook(trusted_webhook)
        self._validate_confirmation_source()

        order = self._require_order(event.order_id)
        self._validate_order_identity(order, event)
        self._validate_amount(order, event)
        self._validate_currency(order, event)

        order_status = self._order_status(order)
        if order_status is OrderStatus.CONFIRMED:
            self._validate_idempotent_confirmation(order, event)
            return PaymentWebhookProcessingResult(order=order, event=event)

        self._validate_confirmation_eligibility(event.payment_status, order_status)
        self._validate_order_transition(order_status)

        updated_order = self.order_repository.record_payment_confirmed(
            order,
            provider_reference=event.payment_provider_reference,
            verified_at=datetime.now(UTC),
        )
        return PaymentWebhookProcessingResult(order=updated_order, event=event)

    def _validate_confirmation_source(self) -> None:
        """Validate that this processor uses a trusted payment-provider source."""
        try:
            validate_payment_confirmation_source(self.event_source)
        except PaymentLifecycleError as exc:
            raise PaymentWebhookProcessingRejected(
                code="invalid_payment_source",
                message=str(exc),
            ) from exc

    def _trusted_payment_event_from_webhook(
        self,
        trusted_webhook: TrustedPaymentWebhook,
    ) -> TrustedPaymentEvent:
        """Parse provider-neutral payment fields from a verified webhook."""
        data = trusted_webhook.payload.get("data")
        if not isinstance(data, dict):
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )

        return TrustedPaymentEvent(
            event_id=trusted_webhook.event_id,
            order_id=self._required_int(data, "order_id"),
            customer_id=self._optional_int(data, "customer_id"),
            payment_status=self._payment_status(data.get("payment_status")),
            payment_provider_reference=self._required_string(
                data,
                "payment_provider_reference",
            ),
            amount=self._required_decimal(data, "amount"),
            currency=self._required_currency(data),
        )

    def _require_order(self, order_id: int) -> Order:
        """Return the referenced Order or reject the payment event."""
        order = self.order_repository.get_order_by_id(order_id)
        if order is None:
            raise PaymentWebhookProcessingRejected(
                code="order_not_found",
                message="Payment webhook references an unknown order.",
            )
        return order

    def _validate_order_identity(
        self, order: Order, event: TrustedPaymentEvent
    ) -> None:
        """Reject payment events that do not match backend order ownership."""
        if event.customer_id is not None and event.customer_id != order.customer_id:
            raise PaymentWebhookProcessingRejected(
                code="payment_customer_mismatch",
                message="Payment webhook customer does not match the order.",
            )

    def _validate_amount(self, order: Order, event: TrustedPaymentEvent) -> None:
        """Reject payment events whose amount differs from backend order total."""
        if event.amount != order.total_amount:
            raise PaymentWebhookProcessingRejected(
                code="payment_amount_mismatch",
                message="Payment webhook amount does not match the order total.",
            )

    def _validate_currency(self, order: Order, event: TrustedPaymentEvent) -> None:
        """Reject payment events whose currency differs from backend order currency."""
        if event.currency != order.currency:
            raise PaymentWebhookProcessingRejected(
                code="payment_currency_mismatch",
                message="Payment webhook currency does not match the order currency.",
            )

    def _validate_idempotent_confirmation(
        self,
        order: Order,
        event: TrustedPaymentEvent,
    ) -> None:
        """Allow already-confirmed same-reference events and reject conflicts."""
        if event.payment_status is not PaymentStatus.VERIFIED:
            raise PaymentWebhookProcessingRejected(
                code="payment_not_verified",
                message="Order confirmation requires a verified payment status.",
            )

        if (
            order.payment_provider_reference == event.payment_provider_reference
            and order.payment_verified_at is not None
        ):
            return

        raise PaymentWebhookProcessingRejected(
            code="payment_reference_conflict",
            message="Payment webhook conflicts with the confirmed order payment.",
        )

    def _validate_confirmation_eligibility(
        self,
        payment_status: PaymentStatus,
        order_status: OrderStatus,
    ) -> None:
        """Validate payment and order state allow draft order confirmation."""
        try:
            validate_order_confirmation_from_payment(
                payment_status,
                order_status,
                event_source=self.event_source,
            )
        except PaymentLifecycleError as exc:
            raise PaymentWebhookProcessingRejected(
                code=self._payment_rejection_code(payment_status, order_status),
                message=str(exc),
            ) from exc

    def _validate_order_transition(self, order_status: OrderStatus) -> None:
        """Validate the order lifecycle transition used for payment confirmation."""
        try:
            transition_order_status(
                order_status,
                OrderStatus.CONFIRMED,
                OrderTransitionTrigger.VERIFIED_PAYMENT,
            )
        except OrderStatusTransitionError as exc:
            raise PaymentWebhookProcessingRejected(
                code="order_transition_rejected",
                message="Payment webhook cannot confirm this order.",
            ) from exc

    @staticmethod
    def _order_status(order: Order) -> OrderStatus:
        """Return the canonical order status or reject unsupported values."""
        try:
            return OrderStatus(order.status)
        except ValueError as exc:
            raise PaymentWebhookProcessingRejected(
                code="invalid_order_status",
                message="Payment webhook references an unsupported order status.",
            ) from exc

    @staticmethod
    def _payment_rejection_code(
        payment_status: PaymentStatus,
        order_status: OrderStatus,
    ) -> str:
        """Return a stable code for payment confirmation eligibility failures."""
        if payment_status is not PaymentStatus.VERIFIED:
            return "payment_not_verified"
        if order_status is not OrderStatus.DRAFT:
            return "order_not_draft"
        return "payment_confirmation_not_allowed"

    @staticmethod
    def _required_int(data: dict[str, Any], field: str) -> int:
        """Return a required integer field from payment event data."""
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )
        return value

    @staticmethod
    def _optional_int(data: dict[str, Any], field: str) -> int | None:
        """Return an optional integer field from payment event data."""
        value = data.get(field)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )
        return value

    @staticmethod
    def _required_string(data: dict[str, Any], field: str) -> str:
        """Return a required non-empty string from payment event data."""
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )
        return value.strip()

    @staticmethod
    def _required_decimal(data: dict[str, Any], field: str) -> Decimal:
        """Return a required decimal amount from payment event data."""
        value = data.get(field)
        if isinstance(value, bool) or value is None:
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            ) from exc

    @staticmethod
    def _required_currency(data: dict[str, Any]) -> str:
        """Return a required uppercase three-letter currency code."""
        currency = PaymentWebhookProcessingService._required_string(data, "currency")
        return currency.upper()

    @staticmethod
    def _payment_status(value: Any) -> PaymentStatus:
        """Return a canonical payment status from payment event data."""
        if not isinstance(value, str):
            raise PaymentWebhookProcessingRejected(
                code="malformed_payment_event",
                message="Payment webhook event data is malformed.",
            )
        try:
            return PaymentStatus(value)
        except ValueError as exc:
            raise PaymentWebhookProcessingRejected(
                code="unsupported_payment_status",
                message="Payment webhook status is unsupported.",
            ) from exc
