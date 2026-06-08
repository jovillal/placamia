from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.order_lifecycle import OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem, OrderItemType
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.checkout import ValidatedCheckoutState
from app.schemas.order import OrderCreateRequest
from app.services.checkout_service import CheckoutEligibilityService, CheckoutRejected
from app.services.pricing_service import PricingItemType

ZERO_MONEY = Decimal("0.00")

FORBIDDEN_FRONTEND_ORDER_CLAIMS: frozenset[str] = frozenset(
    {
        "customer_id",
        "id",
        "user_id",
        "owner_id",
        "role",
        "is_admin",
        "created_at",
        "updated_at",
        "status",
        "cancellation_requested_from",
        "items",
        "order_items",
        "line_items",
        "subtotal",
        "subtotal_amount",
        "discount",
        "discount_amount",
        "tax",
        "tax_amount",
        "total",
        "total_amount",
        "final_amount",
        "checkout_total",
        "currency",
        "payment_provider_reference",
        "payment_verified_at",
        "assigned_provider_id",
        "provider_id",
        "provider_assignment",
        "provider_handoff_reference",
        "provider_handoff_sent_at",
        "provider_cost",
        "provider_quote_reference",
        "provider_pricing_reference",
        "pricing_rule",
        "customer_unit_price",
        "customer_subtotal",
        "preview_total",
        "unit_price_amount",
        "line_subtotal_amount",
        "line_discount_amount",
        "line_tax_amount",
        "line_total_amount",
        "provider_payload_snapshot",
        "terms_policy_version",
        "payment",
        "payment_status",
        "provider_handoff",
    }
)
"""Frontend-owned fields that must not influence draft order creation."""


@dataclass(frozen=True)
class OrderCreationRejected(ValueError):
    """Raised when draft order creation rejects a request.

    Attributes:
        code: Stable rejection reason for routes, services, and tests.
        message: Human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


class OrderCreationService:
    """Create draft orders from backend-validated checkout state.

    The service rejects frontend-owned security claims, delegates eligibility,
    pricing, provider capability, and terms validation to the #101 checkout
    service, then persists a draft Order and immutable OrderItem snapshots. It
    does not initialize payments, verify payments, or send provider handoffs.
    """

    def __init__(
        self,
        checkout_service: CheckoutEligibilityService,
        order_repository: OrderRepository,
    ) -> None:
        """Store draft order creation dependencies.

        Args:
            checkout_service: Service that returns backend-validated checkout
                state or rejects the request before mutation.
            order_repository: Repository used to persist the draft order and
                item snapshots.
        """
        self.checkout_service = checkout_service
        self.order_repository = order_repository

    def create_draft_order(
        self,
        request: OrderCreateRequest,
        current_user: User,
    ) -> Order:
        """Validate checkout input and persist a draft order for current_user.

        Args:
            request: Public order creation request body.
            current_user: Authenticated user resolved from request context.

        Returns:
            Persisted draft Order with immutable item snapshots.

        Raises:
            OrderCreationRejected: If frontend-owned claims are present,
                checkout validation rejects the request, or snapshot source
                data is unavailable.

        Side effects:
            Creates one Order and one or more OrderItems only after all
            validation succeeds. It never writes payment verification or
            provider handoff fields.
        """
        self._reject_frontend_order_claims(request.frontend_claims())

        try:
            checkout_state = self.checkout_service.validate_checkout(request)
        except CheckoutRejected as exc:
            raise OrderCreationRejected(code=exc.code, message=exc.message) from exc

        order = self._order_from_checkout_state(checkout_state, current_user)
        item = self._order_item_from_checkout_state(checkout_state)
        return self.order_repository.create_order(order, [item])

    def _reject_frontend_order_claims(self, frontend_claims: dict[str, Any]) -> None:
        """Reject frontend-owned order, payment, provider, or snapshot claims."""
        if not frontend_claims:
            return

        if set(frontend_claims) & FORBIDDEN_FRONTEND_ORDER_CLAIMS:
            raise OrderCreationRejected(
                code="frontend_order_claim_not_allowed",
                message=(
                    "Frontend ownership, status, payment, provider handoff, "
                    "pricing, or order snapshot claims are not accepted."
                ),
            )

    def _order_from_checkout_state(
        self,
        checkout_state: ValidatedCheckoutState,
        current_user: User,
    ) -> Order:
        """Build a draft Order from backend-owned checkout state."""
        return Order(
            customer_id=current_user.id,
            status=OrderStatus.DRAFT.value,
            subtotal_amount=checkout_state.customer_subtotal,
            discount_amount=ZERO_MONEY,
            tax_amount=ZERO_MONEY,
            total_amount=checkout_state.preview_total,
            currency=checkout_state.currency,
            assigned_provider_id=checkout_state.assigned_provider_id,
            terms_policy_version=checkout_state.terms_policy_version,
        )

    def _order_item_from_checkout_state(
        self,
        checkout_state: ValidatedCheckoutState,
    ) -> OrderItem:
        """Build an immutable OrderItem snapshot from validated checkout state."""
        if checkout_state.item_type is not PricingItemType.PRODUCT:
            raise OrderCreationRejected(
                code="unsupported_order_item_type",
                message="Draft order creation currently supports product items only.",
            )

        if checkout_state.product_id is None:
            raise OrderCreationRejected(
                code="invalid_checkout_snapshot",
                message="Validated checkout state is missing product snapshot data.",
            )

        return self._product_order_item(checkout_state)

    def _product_order_item(
        self,
        checkout_state: ValidatedCheckoutState,
    ) -> OrderItem:
        """Build one product OrderItem snapshot from checkout-owned state."""
        provider_payload_snapshot: dict[str, Any] = {
            "item_type": OrderItemType.PRODUCT,
            "product_id": checkout_state.product_id,
            "display_name": checkout_state.display_name,
            "selected_options": checkout_state.selected_options,
            "quantity": checkout_state.quantity,
            "provider_quote_reference": checkout_state.provider_quote_reference,
        }

        return OrderItem(
            item_type=OrderItemType.PRODUCT,
            product_id=checkout_state.product_id,
            display_name=checkout_state.display_name,
            customer_safe_description=checkout_state.customer_safe_description,
            selected_options=checkout_state.selected_options,
            quantity=checkout_state.quantity,
            unit_price_amount=checkout_state.customer_unit_price,
            line_subtotal_amount=checkout_state.customer_subtotal,
            line_discount_amount=ZERO_MONEY,
            line_tax_amount=ZERO_MONEY,
            line_total_amount=checkout_state.preview_total,
            currency=checkout_state.currency,
            assigned_provider_id=checkout_state.assigned_provider_id,
            provider_pricing_reference=checkout_state.provider_quote_reference,
            provider_payload_snapshot=provider_payload_snapshot,
        )
