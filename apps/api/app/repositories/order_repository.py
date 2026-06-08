from __future__ import annotations

from collections.abc import Iterable

from app.models.order import Order
from app.models.order_item import OrderItem
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


class OrderRepository:
    """Data access layer for persisted customer orders and item snapshots.

    The repository receives a SQLAlchemy session and writes already
    backend-validated order data. It does not authenticate users, accept
    frontend ownership claims, calculate prices, initialize payments, or send
    provider handoffs.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by order queries and writes.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def create_order(self, order: Order, items: Iterable[OrderItem]) -> Order:
        """Persist an order with immutable item snapshots.

        Args:
            order: Order model populated from backend-validated checkout state.
            items: OrderItem snapshots populated from backend-calculated pricing
                and persisted catalog/design data.

        Returns:
            The persisted Order with database-generated identifiers populated.

        Side effects:
            Adds the order and item rows to the current database transaction and
            commits it.
        """
        order.items = list(items)
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def get_order_by_id(self, order_id: int) -> Order | None:
        """Return one order by primary key.

        Args:
            order_id: Order identifier to look up.

        Returns:
            The matching order model instance, or None when no order exists.
        """
        return self.db.get(Order, order_id)

    def get_order_for_customer(self, order_id: int, customer_id: int) -> Order | None:
        """Return one order owned by an authenticated customer with items loaded.

        Args:
            order_id: Order identifier to look up.
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            The matching customer-owned Order with item snapshots loaded, or
            None when no such order exists.
        """
        result = self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    def get_orders_for_customer(self, customer_id: int) -> list[Order]:
        """Return orders owned by one authenticated customer id.

        Args:
            customer_id: Backend-derived customer identifier.

        Returns:
            Matching orders sorted by newest first.
        """
        result = self.db.execute(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
        return list(result.scalars().all())
