from dataclasses import dataclass

from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories.order_repository import OrderRepository


@dataclass(frozen=True)
class CustomerOrderDetail:
    """One customer-owned Order and its ordered immutable item snapshots."""

    order: Order
    items: tuple[OrderItem, ...]


class OrderDetailService:
    """Coordinate owner-scoped deterministic customer Order detail reads."""

    def __init__(self, order_repository: OrderRepository) -> None:
        """Store the repository used for customer Order detail reads.

        Args:
            order_repository: Repository that applies owner scoping and loads
                approved persisted snapshot columns.
        """
        self.order_repository = order_repository

    def get_customer_order_detail(
        self,
        *,
        order_id: int,
        customer_id: int,
    ) -> CustomerOrderDetail | None:
        """Return one owned Order with item snapshots ordered by row id.

        Args:
            order_id: Order identifier from the customer route.
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            Customer-owned persisted detail with immutable items ordered by
            OrderItem id, or None when the owner-scoped Order does not exist.

        Side effects:
            Reads Order detail through the repository. No model or persistence
            state is mutated.
        """
        order = self.order_repository.get_order_detail_for_customer(
            order_id,
            customer_id,
        )
        if order is None:
            return None

        return CustomerOrderDetail(
            order=order,
            items=tuple(sorted(order.items, key=lambda item: item.id)),
        )
