from dataclasses import dataclass

from app.models.order import Order
from app.repositories.order_repository import OrderRepository


@dataclass(frozen=True)
class CustomerOrderPage:
    """One owner-scoped page of persisted customer Order summaries."""

    orders: list[Order]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class OrderListService:
    """Coordinate deterministic owner-scoped Order list pagination."""

    def __init__(self, order_repository: OrderRepository) -> None:
        """Store the repository used for customer Order list reads.

        Args:
            order_repository: Repository that performs owner-scoped list and
                count queries.
        """
        self.order_repository = order_repository

    def list_customer_orders(
        self,
        *,
        customer_id: int,
        page: int,
        page_size: int,
    ) -> CustomerOrderPage:
        """Return one page of persisted Orders owned by a customer.

        Args:
            customer_id: Backend-derived authenticated customer identifier.
            page: One-based page number validated by the API boundary.
            page_size: Bounded page size validated by the API boundary.

        Returns:
            Owner-scoped Order summaries with deterministic pagination totals.

        Side effects:
            Executes owner-scoped Order list and count database reads through
            the repository. No state is mutated.
        """
        offset = (page - 1) * page_size
        orders = self.order_repository.get_orders_page_for_customer(
            customer_id,
            offset=offset,
            limit=page_size,
        )
        total_items = self.order_repository.count_orders_for_customer(customer_id)
        total_pages = (total_items + page_size - 1) // page_size if total_items else 0
        return CustomerOrderPage(
            orders=orders,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )
