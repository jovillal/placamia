from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.domain.provider_adapter import PaidOrderHandoffRequest
from app.models.order import Order
from app.models.order_item import OrderItem

HANDOFF_CONTRACT_VERSION = "paid_order_handoff_v1"
"""Current provider-neutral paid-order handoff payload contract version."""

DEFERRED_DELIVERY_FIELDS = (
    "recipient_name",
    "address",
    "phone",
    "email",
    "delivery_instructions",
)
"""Delivery/contact fields deferred until they are modeled and persisted."""

FORBIDDEN_PROVIDER_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "assigned_provider_id",
        "address",
        "audit",
        "audit_log",
        "card",
        "card_data",
        "checkout_total",
        "customer_subtotal",
        "customer_total",
        "customer_unit_price",
        "customer",
        "customer_email",
        "customer_id",
        "discount",
        "discount_amount",
        "delivery_address",
        "delivery_instructions",
        "email",
        "final_amount",
        "frontend_claims",
        "frontend_provider_id",
        "frontend_provider_assignment",
        "frontend_provider_claims",
        "line_discount_amount",
        "line_subtotal_amount",
        "line_tax_amount",
        "line_total_amount",
        "margin",
        "internal",
        "internal_audit",
        "owner_id",
        "payment",
        "payment_provider_reference",
        "payment_verified_at",
        "phone",
        "provider_assignment",
        "provider_cost",
        "provider_id",
        "provider_pricing_reference",
        "provider_quote_reference",
        "raw_frontend_data",
        "raw_provider_pricing_data",
        "recipient_name",
        "role",
        "secret",
        "tax",
        "tax_amount",
        "terms_policy_version",
        "token",
        "total",
        "total_amount",
        "unit_price_amount",
        "user_id",
    }
)
"""Fields that must never be forwarded in provider handoff payload snapshots."""


@dataclass(frozen=True)
class ProviderHandoffPayloadRejected(ValueError):
    """Raised when paid-order handoff payload preparation is rejected.

    Attributes:
        code: Stable rejection reason for routes, services, and tests.
        message: Human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


class ProviderHandoffPayloadService:
    """Prepare provider-neutral paid-order handoff payloads from snapshots.

    The service validates backend-owned eligibility inputs, then builds a
    provider adapter request from persisted Order and OrderItem snapshot data.
    It does not transmit the payload, update order state, persist provider
    responses, verify payments, or regenerate provider payload snapshots from
    mutable catalog/pricing/provider/frontend data.
    """

    def prepare_handoff_request(
        self,
        order: Order,
        payment_status: PaymentStatus,
        *,
        handoff_attempt_id: str | None = None,
    ) -> PaidOrderHandoffRequest:
        """Build a paid-order provider handoff request without side effects.

        Args:
            order: Persisted Order with item snapshots loaded.
            payment_status: Backend-owned payment status after payment
                lifecycle validation.
            handoff_attempt_id: Optional trace id for this preparation attempt.
                When omitted, a new UUID-based attempt id is generated.

        Returns:
            A provider adapter handoff request containing the provider-neutral
            payload, stable idempotency key, and backend provider assignment.

        Raises:
            ProviderHandoffPayloadRejected: If payment, order, provider
                assignment, item, or snapshot data is not handoff-ready.

        Side effects:
            None. The service reads the supplied persisted objects and returns a
            request value. It never mutates Order, OrderItem, payment, or
            provider handoff state.
        """
        self._validate_payment_status(payment_status)
        self._validate_payment_verification_timestamp(order)
        self._validate_order_status(order)
        items = self._validated_items(order)
        assigned_provider_id = self._assigned_provider_id(order, items)
        attempt_id = handoff_attempt_id or str(uuid4())
        idempotency_key = self._idempotency_key(order.id, assigned_provider_id)

        payload: dict[str, Any] = {
            "contract_version": HANDOFF_CONTRACT_VERSION,
            "correlation": {
                "order_id": order.id,
                "assigned_provider_id": assigned_provider_id,
                "handoff_attempt_id": attempt_id,
                "idempotency_key": idempotency_key,
            },
            "eligibility": {
                "payment_status": payment_status.value,
                "order_status": order.status,
            },
            "provider_assignment": {
                "assigned_provider_id": assigned_provider_id,
            },
            "order": {
                "id": order.id,
                "created_at": order.created_at.isoformat(),
            },
            "items": [self._item_payload(item, assigned_provider_id) for item in items],
            "delivery": {
                "status": "deferred",
                "deferred_fields": list(DEFERRED_DELIVERY_FIELDS),
            },
            "shipment": {
                "qr_reference": None,
                "carrier_reference": None,
                "deferred_fields": ["qr_reference"],
            },
        }

        return PaidOrderHandoffRequest(
            order_id=order.id,
            assigned_provider_id=assigned_provider_id,
            idempotency_key=idempotency_key,
            payload=payload,
        )

    def _validate_payment_status(self, payment_status: PaymentStatus) -> None:
        """Reject payload preparation unless payment is verified."""
        if payment_status is not PaymentStatus.VERIFIED:
            raise ProviderHandoffPayloadRejected(
                code="payment_not_verified",
                message="Provider handoff payload requires verified payment.",
            )

    def _validate_order_status(self, order: Order) -> None:
        """Reject payload preparation unless the order is confirmed."""
        if order.status != OrderStatus.CONFIRMED.value:
            raise ProviderHandoffPayloadRejected(
                code="order_not_confirmed",
                message="Provider handoff payload requires confirmed order status.",
            )

    def _validate_payment_verification_timestamp(self, order: Order) -> None:
        """Reject payload preparation without backend payment verification time."""
        if order.payment_verified_at is None:
            raise ProviderHandoffPayloadRejected(
                code="payment_verification_timestamp_required",
                message=(
                    "Provider handoff request requires persisted payment "
                    "verification timestamp."
                ),
            )

    def _validated_items(self, order: Order) -> list[OrderItem]:
        """Return loaded order items or reject missing item snapshots."""
        items = list(getattr(order, "items", []) or [])
        if not items:
            raise ProviderHandoffPayloadRejected(
                code="order_items_required",
                message="Provider handoff payload requires at least one order item.",
            )

        return items

    def _assigned_provider_id(self, order: Order, items: list[OrderItem]) -> str:
        """Resolve backend-owned provider assignment from order or item data."""
        if order.assigned_provider_id and order.assigned_provider_id.strip():
            return order.assigned_provider_id.strip()

        item_provider_ids = {
            item.assigned_provider_id.strip()
            for item in items
            if item.assigned_provider_id and item.assigned_provider_id.strip()
        }
        if len(item_provider_ids) == 1:
            return next(iter(item_provider_ids))

        raise ProviderHandoffPayloadRejected(
            code="provider_assignment_required",
            message="Provider handoff payload requires backend provider assignment.",
        )

    def _item_payload(
        self,
        item: OrderItem,
        assigned_provider_id: str,
    ) -> dict[str, Any]:
        """Build one provider-neutral item payload from an OrderItem snapshot."""
        if item.assigned_provider_id != assigned_provider_id:
            raise ProviderHandoffPayloadRejected(
                code="provider_assignment_mismatch",
                message="Order item provider assignment does not match the order.",
            )

        provider_payload_snapshot = self._provider_payload_snapshot(item)

        return {
            "order_item_id": item.id,
            "item_type": item.item_type,
            "display_name": item.display_name,
            "customer_safe_description": item.customer_safe_description,
            "quantity": item.quantity,
            "selected_options": item.selected_options,
            "references": {
                key: value
                for key, value in {
                    "product_id": item.product_id,
                    "kit_id": item.kit_id,
                    "template_id": item.template_id,
                    "design_id": item.design_id,
                }.items()
                if value is not None
            },
            "provider_payload_snapshot": provider_payload_snapshot,
        }

    def _provider_payload_snapshot(self, item: OrderItem) -> dict[str, Any]:
        """Return a filtered manufacturing-safe provider payload snapshot."""
        snapshot = item.provider_payload_snapshot
        if not isinstance(snapshot, dict) or not snapshot:
            raise ProviderHandoffPayloadRejected(
                code="provider_payload_snapshot_required",
                message=(
                    "Provider handoff payload requires persisted manufacturing "
                    "snapshot data."
                ),
            )

        filtered_snapshot = self._filter_forbidden_snapshot_fields(snapshot)
        if not filtered_snapshot:
            raise ProviderHandoffPayloadRejected(
                code="provider_payload_snapshot_required",
                message=(
                    "Provider handoff payload requires manufacturing-safe "
                    "snapshot data."
                ),
            )

        return filtered_snapshot

    def _filter_forbidden_snapshot_fields(self, value: Any) -> Any:
        """Recursively remove forbidden provider payload snapshot fields."""
        if isinstance(value, dict):
            return {
                key: self._filter_forbidden_snapshot_fields(nested_value)
                for key, nested_value in value.items()
                if key not in FORBIDDEN_PROVIDER_PAYLOAD_KEYS
            }

        if isinstance(value, list):
            return [
                self._filter_forbidden_snapshot_fields(item_value)
                for item_value in value
            ]

        return value

    @staticmethod
    def _idempotency_key(order_id: int, assigned_provider_id: str) -> str:
        """Return the stable idempotency key for one Order/provider handoff."""
        return f"order:{order_id}:provider:{assigned_provider_id}"
