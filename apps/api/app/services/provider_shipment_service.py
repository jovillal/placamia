from __future__ import annotations

from dataclasses import dataclass

from app.domain.order_lifecycle import (
    OrderStatus,
    OrderStatusTransitionError,
    OrderTransitionTrigger,
    transition_order_status,
)
from app.domain.provider_shipment import ProviderShipmentEvent
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.order_repository import OrderRepository

PROVIDER_SHIPMENT_AUDIT_ACTION = "provider.shipment.record"
"""Stable audit action for admin-ingested provider shipment events."""


class ProviderShipmentRejected(ValueError):
    """Raised when provider shipment processing is rejected.

    Attributes:
        code: Stable machine-readable rejection reason for routes and tests.
        message: Safe human-readable rejection message.
    """

    def __init__(self, code: str, message: str) -> None:
        """Store a stable rejection code and safe message.

        Args:
            code: Stable machine-readable rejection reason.
            message: Safe human-readable rejection message.

        Side effects:
            None.
        """
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderShipmentResult:
    """Result of processing one provider shipment event.

    Attributes:
        order: Current Order after processing.
        event: Backend-owned shipment event.
        from_status: Order status before the first accepted transition.
        target_status: Order status represented by the event.
        trigger: Lifecycle trigger used for non-idempotent persistence.
        event_reference: Optional carrier/backend event reference.
        idempotent: Whether the persisted state already represented the event.
    """

    order: Order
    event: ProviderShipmentEvent
    from_status: OrderStatus
    target_status: OrderStatus
    trigger: OrderTransitionTrigger
    event_reference: str | None = None
    idempotent: bool = False


class ProviderShipmentService:
    """Persist admin-ingested provider shipment events for paid orders.

    The service consumes backend-owned MVP shipment events for orders already
    ready for pickup. It rejects frontend/customer status claims, keeps payment
    fields untouched, validates lifecycle moves through the order lifecycle
    boundary, and uses existing audit logs for minimal event-reference replay
    detection. Idempotent replays do not mutate order state, but callers may
    still audit the replay attempt.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        """Store repository dependencies.

        Args:
            order_repository: Repository used to load and stage order updates.
            audit_log_repository: Repository used to inspect prior shipment
                audit metadata for duplicate event references.

        Side effects:
            None.
        """
        self.order_repository = order_repository
        self.audit_log_repository = audit_log_repository

    def process_shipment(
        self,
        order_id: int,
        event: ProviderShipmentEvent,
        *,
        event_reference: str | None = None,
    ) -> ProviderShipmentResult:
        """Record one provider shipment event.

        Args:
            order_id: Persisted order identifier.
            event: Backend-owned shipment event.
            event_reference: Optional carrier/backend event reference for
                traceability and duplicate detection.

        Returns:
            Processing result containing current order and transition metadata.

        Side effects:
            For eligible orders, stages an order status update and flushes the
            current transaction. Idempotent replays do not mutate the order;
            the endpoint may still record the replay attempt in the audit log.

        Raises:
            ProviderShipmentRejected: If the order is missing, the lifecycle
                state is invalid, or the event reference conflicts with a prior
                shipment event.
        """
        order = self.order_repository.get_order_by_id(order_id)
        if order is None:
            raise ProviderShipmentRejected(
                code="order_not_found",
                message="Order was not found.",
            )

        normalized_event_reference = self._normalized_event_reference(
            event_reference,
        )
        transition_metadata = self._transition_metadata(event)
        duplicate_result = self._duplicate_event_reference_result(
            order,
            event,
            transition_metadata,
            normalized_event_reference,
        )
        if duplicate_result is not None:
            return duplicate_result

        order_status = self._order_status(order)
        try:
            transition_order_status(
                order_status,
                transition_metadata.target_status,
                transition_metadata.trigger,
            )
        except OrderStatusTransitionError as exc:
            raise ProviderShipmentRejected(
                code="order_not_ready_for_pickup",
                message="Shipment requires a ready-for-pickup order.",
            ) from exc

        updated_order = self.order_repository.record_provider_shipment(
            order,
            status=transition_metadata.target_status,
        )
        return ProviderShipmentResult(
            order=updated_order,
            event=event,
            from_status=order_status,
            target_status=transition_metadata.target_status,
            trigger=transition_metadata.trigger,
            event_reference=normalized_event_reference,
            idempotent=False,
        )

    @staticmethod
    def _normalized_event_reference(event_reference: str | None) -> str | None:
        """Return a stripped event reference or None."""
        if event_reference is None:
            return None

        stripped_event_reference = event_reference.strip()
        return stripped_event_reference or None

    @staticmethod
    def _order_status(order: Order) -> OrderStatus:
        """Return the canonical order status or reject unsupported values."""
        try:
            return OrderStatus(order.status)
        except ValueError as exc:
            raise ProviderShipmentRejected(
                code="invalid_order_status",
                message="Order has an unsupported status.",
            ) from exc

    def _duplicate_event_reference_result(
        self,
        order: Order,
        event: ProviderShipmentEvent,
        transition_metadata: "_ShipmentTransitionMetadata",
        event_reference: str | None,
    ) -> ProviderShipmentResult | None:
        """Return order-state-idempotent duplicate result or reject conflicts."""
        if event_reference is None:
            return None

        matching_audit_log = self._matching_event_reference_log(
            order.id,
            event_reference,
        )
        if matching_audit_log is None:
            return None

        prior_event = matching_audit_log.event_details.get("event")
        prior_target_status = matching_audit_log.event_details.get("target_status")
        if prior_event != event.value:
            raise ProviderShipmentRejected(
                code="event_reference_conflict",
                message="Shipment event reference conflicts.",
            )

        order_status = self._order_status(order)
        if (
            prior_target_status == transition_metadata.target_status.value
            and order_status is transition_metadata.target_status
        ):
            prior_from_status = self._safe_order_status(
                matching_audit_log.event_details.get("from_status"),
                fallback=transition_metadata.from_status,
            )
            return ProviderShipmentResult(
                order=order,
                event=event,
                from_status=prior_from_status,
                target_status=transition_metadata.target_status,
                trigger=transition_metadata.trigger,
                event_reference=event_reference,
                idempotent=True,
            )

        raise ProviderShipmentRejected(
            code="event_reference_status_conflict",
            message="Shipment event reference does not match order state.",
        )

    def _matching_event_reference_log(
        self,
        order_id: int,
        event_reference: str,
    ) -> AuditLog | None:
        """Return a prior shipment audit log by event reference."""
        for audit_log in self.audit_log_repository.get_audit_logs_for_resource_action(
            action=PROVIDER_SHIPMENT_AUDIT_ACTION,
            resource_type="order",
            resource_id=order_id,
        ):
            if audit_log.event_details.get("event_reference") == event_reference:
                return audit_log

        return None

    @staticmethod
    def _safe_order_status(value: object, *, fallback: OrderStatus) -> OrderStatus:
        """Return a stored order status value or a safe fallback."""
        try:
            return OrderStatus(value)
        except ValueError:
            return fallback

    @staticmethod
    def _transition_metadata(
        event: ProviderShipmentEvent,
    ) -> "_ShipmentTransitionMetadata":
        """Return lifecycle metadata for a shipment event."""
        if event is ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN:
            return _ShipmentTransitionMetadata(
                from_status=OrderStatus.READY_FOR_PICKUP,
                target_status=OrderStatus.SHIPPED,
                trigger=OrderTransitionTrigger.CARRIER_QR_PICKUP_SCAN,
            )

        return _ShipmentTransitionMetadata(
            from_status=OrderStatus.READY_FOR_PICKUP,
            target_status=OrderStatus.SHIPPED,
            trigger=OrderTransitionTrigger.AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK,
        )


@dataclass(frozen=True)
class _ShipmentTransitionMetadata:
    """Lifecycle metadata for one shipment event."""

    from_status: OrderStatus
    target_status: OrderStatus
    trigger: OrderTransitionTrigger
