from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.models.order import Order
from app.services.provider_handoff_transmission_service import (
    ProviderHandoffTransmissionRejected,
    ProviderHandoffTransmissionService,
)

logger = logging.getLogger(__name__)


class PaidOrderHandoffOrchestrationState(StrEnum):
    """Provider handoff orchestration outcomes for a paid order."""

    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PaidOrderHandoffOrchestrationResult:
    """Result of attempting paid-order provider handoff orchestration.

    Attributes:
        order: Current Order after orchestration. Successful handoff returns
            the persisted `sent_to_provider` Order. Failed and skipped
            orchestration return the original Order without payment rollback.
        state: Stable orchestration outcome.
        provider_reference: Provider handoff reference when transmission
            succeeded.
        idempotency_key: Stable handoff idempotency key when transmission
            reached the provider handoff boundary.
        rejection_code: Stable skip or failure reason for callers and tests.
        reason_code: Optional provider or transmission reason code.
    """

    order: Order
    state: PaidOrderHandoffOrchestrationState
    provider_reference: str | None = None
    idempotency_key: str | None = None
    rejection_code: str | None = None
    reason_code: str | None = None


class PaidOrderHandoffOrchestrationService:
    """Trigger provider handoff for already-confirmed paid orders.

    This service is the #132 coordinator between payment confirmation and the
    #61 provider handoff transmission boundary. It consumes an already
    confirmed Order/payment state, skips ineligible orders without touching the
    adapter, delegates eligible transmission to #61, and keeps successful
    payment confirmation valid when handoff transmission fails.
    """

    def __init__(
        self,
        transmission_service: ProviderHandoffTransmissionService,
    ) -> None:
        """Store the provider handoff transmission dependency.

        Args:
            transmission_service: Existing #61 service responsible for payload
                preparation, adapter transmission, and successful handoff
                persistence.

        Side effects:
            None.
        """
        self.transmission_service = transmission_service

    def orchestrate_confirmed_paid_order(
        self,
        order: Order,
        payment_status: PaymentStatus,
    ) -> PaidOrderHandoffOrchestrationResult:
        """Attempt provider handoff for one confirmed paid Order.

        Args:
            order: Persisted Order returned by payment confirmation or loaded
                for retry orchestration.
            payment_status: Backend-owned payment status from the trusted
                payment confirmation path.

        Returns:
            A sent, failed, or skipped orchestration result. Handoff failures
            are reported as retryable results instead of invalidating payment
            confirmation.

        Side effects:
            Eligible orders are delegated to the provider handoff transmission
            service. Successful transmission records provider handoff fields
            and moves the Order to `sent_to_provider`. Failed and skipped
            orchestration does not mutate payment fields or roll the Order back
            to `draft`.
        """
        skip_code = self._skip_code(order, payment_status)
        if skip_code is not None:
            self._log_skipped(order, skip_code)
            return PaidOrderHandoffOrchestrationResult(
                order=order,
                state=PaidOrderHandoffOrchestrationState.SKIPPED,
                rejection_code=skip_code,
            )

        try:
            transmission_result = self.transmission_service.transmit_paid_order(
                order,
                payment_status,
            )
        except ProviderHandoffTransmissionRejected as exc:
            self._log_failed(order, exc)
            return PaidOrderHandoffOrchestrationResult(
                order=order,
                state=PaidOrderHandoffOrchestrationState.FAILED,
                rejection_code=exc.code,
                reason_code=exc.reason_code,
            )

        self._log_sent(
            transmission_result.order,
            transmission_result.idempotency_key,
            transmission_result.provider_reference,
        )
        return PaidOrderHandoffOrchestrationResult(
            order=transmission_result.order,
            state=PaidOrderHandoffOrchestrationState.SENT,
            provider_reference=transmission_result.provider_reference,
            idempotency_key=transmission_result.idempotency_key,
        )

    @staticmethod
    def _skip_code(order: Order, payment_status: PaymentStatus) -> str | None:
        """Return a skip reason when the order must not trigger handoff."""
        if payment_status is not PaymentStatus.VERIFIED:
            return "payment_not_verified"

        try:
            order_status = OrderStatus(order.status)
        except ValueError:
            return "invalid_order_status"

        if order_status is not OrderStatus.CONFIRMED:
            return "order_not_confirmed"

        if order.payment_verified_at is None:
            return "payment_verification_timestamp_required"

        return None

    @staticmethod
    def _log_skipped(order: Order, rejection_code: str) -> None:
        """Log skipped orchestration without sensitive payment/customer data."""
        logger.info(
            "provider_handoff_orchestration_skipped order_id=%s rejection_code=%s",
            order.id,
            rejection_code,
        )

    @staticmethod
    def _log_failed(order: Order, exc: ProviderHandoffTransmissionRejected) -> None:
        """Log failed orchestration without sensitive payment/customer data."""
        logger.warning(
            "provider_handoff_orchestration_failed order_id=%s "
            "rejection_code=%s reason_code=%s",
            order.id,
            exc.code,
            exc.reason_code,
        )

    @staticmethod
    def _log_sent(
        order: Order,
        idempotency_key: str,
        provider_reference: str,
    ) -> None:
        """Log successful orchestration without sensitive payment/customer data."""
        logger.info(
            "provider_handoff_orchestration_sent order_id=%s "
            "idempotency_key=%s provider_reference=%s",
            order.id,
            idempotency_key,
            provider_reference,
        )
