from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from app.domain.order_lifecycle import OrderStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, raiseload, selectinload


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

    def get_orders_page_for_customer(
        self,
        customer_id: int,
        *,
        offset: int,
        limit: int,
    ) -> list[Order]:
        """Return one scalar-only page of an authenticated customer's Orders.

        Args:
            customer_id: Backend-derived authenticated customer identifier.
            offset: Number of matching owner-scoped Orders to skip.
            limit: Maximum number of matching Orders to return.

        Returns:
            Customer-owned Orders ordered by creation time and id descending.

        Side effects:
            Reads persisted Order summary columns only. Related customer,
            OrderItem, and Payment rows are not loaded.
        """
        result = self.db.execute(
            select(Order)
            .options(
                load_only(
                    Order.id,
                    Order.status,
                    Order.currency,
                    Order.total_amount,
                    Order.created_at,
                    Order.updated_at,
                    raiseload=True,
                ),
                raiseload("*"),
            )
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    def count_orders_for_customer(self, customer_id: int) -> int:
        """Count Orders owned by one authenticated customer.

        Args:
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            Number of persisted Orders owned by the customer.

        Side effects:
            Executes one owner-scoped aggregate database read.
        """
        return self.db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.customer_id == customer_id)
        )

    def record_provider_handoff_sent(
        self,
        order: Order,
        *,
        provider_reference: str,
        sent_at: datetime,
    ) -> Order:
        """Persist successful provider handoff transmission fields.

        Args:
            order: Validated confirmed Order that was sent through the
                provider adapter boundary.
            provider_reference: Provider-side handoff reference returned by
                the adapter.
            sent_at: Backend timestamp for the successful transmission.

        Returns:
            The refreshed Order after status and handoff trace fields are
            committed.

        Side effects:
            Updates order status, provider handoff reference, and handoff sent
            timestamp, then commits the current database transaction.
        """
        order.status = OrderStatus.SENT_TO_PROVIDER.value
        order.provider_handoff_reference = provider_reference
        order.provider_handoff_sent_at = sent_at
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def record_payment_confirmed(
        self,
        order: Order,
        *,
        provider_reference: str,
        verified_at: datetime,
    ) -> Order:
        """Persist successful payment confirmation fields for an order.

        Args:
            order: Validated draft Order that may move to confirmed after a
                trusted payment-provider event.
            provider_reference: Payment-provider reference from the verified
                webhook event.
            verified_at: Backend timestamp for the successful verification.

        Returns:
            The refreshed Order after payment fields and status are flushed.

        Side effects:
            Updates order status, payment provider reference, and payment
            verification timestamp, then flushes the current transaction. The
            caller remains responsible for committing or rolling back.
        """
        order.status = OrderStatus.CONFIRMED.value
        order.payment_provider_reference = provider_reference
        order.payment_verified_at = verified_at
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order

    def record_provider_acceptance_outcome(
        self,
        order: Order,
        *,
        status: OrderStatus,
    ) -> Order:
        """Persist a provider acceptance/rejection lifecycle outcome.

        Args:
            order: Validated Order whose provider handoff has already been sent.
            status: Lifecycle status validated for the provider decision.

        Returns:
            The Order after the status update has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and flushes the current
            database transaction. The caller remains responsible for committing
            or rolling back so provider decision persistence can stay atomic
            with its audit log. Payment confirmation fields and provider
            handoff trace fields are intentionally left untouched.
        """
        order.status = status.value
        order.cancellation_requested_from = None
        self.db.add(order)
        self.db.flush()
        return order

    def record_provider_production_progress(
        self,
        order: Order,
        *,
        status: OrderStatus,
    ) -> Order:
        """Stage a provider production-progress lifecycle outcome.

        Args:
            order: Validated Order whose production progress event is allowed.
            status: Lifecycle status validated for the production event.

        Returns:
            The Order after the status update has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and flushes the current
            database transaction. The caller remains responsible for committing
            or rolling back so production progress persistence can stay atomic
            with its audit log. Payment confirmation and provider handoff trace
            fields are intentionally left untouched.
        """
        order.status = status.value
        order.cancellation_requested_from = None
        self.db.add(order)
        self.db.flush()
        return order

    def record_provider_shipment(
        self,
        order: Order,
        *,
        status: OrderStatus,
    ) -> Order:
        """Stage a provider shipment lifecycle outcome.

        Args:
            order: Validated Order whose shipment event is allowed.
            status: Lifecycle status validated for the shipment event.

        Returns:
            The Order after the status update has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and flushes the current
            database transaction. The caller remains responsible for committing
            or rolling back so shipment persistence can stay atomic with its
            audit log. Payment confirmation and provider handoff trace fields
            are intentionally left untouched.
        """
        order.status = status.value
        order.cancellation_requested_from = None
        self.db.add(order)
        self.db.flush()
        return order

    def record_provider_delivery(
        self,
        order: Order,
        *,
        status: OrderStatus,
    ) -> Order:
        """Stage a provider delivery lifecycle outcome.

        Args:
            order: Validated Order whose delivery event is allowed.
            status: Lifecycle status validated for the delivery event.

        Returns:
            The Order after the status update has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and flushes the current
            database transaction. The caller remains responsible for committing
            or rolling back so delivery persistence can stay atomic with its
            audit log. Payment confirmation, provider handoff trace, and
            shipment history fields are intentionally left untouched.
        """
        order.status = status.value
        order.cancellation_requested_from = None
        self.db.add(order)
        self.db.flush()
        return order

    def record_customer_cancellation_request(
        self,
        order: Order,
        *,
        from_status: OrderStatus,
    ) -> Order:
        """Stage a paid-order cancellation request.

        Args:
            order: Validated customer-owned Order eligible for a cancellation
                request.
            from_status: Paid lifecycle status that should be restored if an
                admin later rejects the request.

        Returns:
            The Order after the request state has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and
            `cancellation_requested_from`, then flushes the current database
            transaction. The caller remains responsible for committing or
            rolling back so the request stays atomic with its audit log.
            Payment confirmation and provider fulfillment trace fields are left
            untouched.
        """
        order.status = OrderStatus.CANCELLATION_REQUESTED.value
        order.cancellation_requested_from = from_status.value
        self.db.add(order)
        self.db.flush()
        return order

    def resolve_customer_cancellation_request(
        self,
        order: Order,
        *,
        status: OrderStatus,
    ) -> Order:
        """Stage an admin resolution for a cancellation request.

        Args:
            order: Validated Order currently in `cancellation_requested`.
            status: Lifecycle status validated for the resolution outcome.

        Returns:
            The Order after the resolution state has been staged and flushed.

        Side effects:
            Updates only the order lifecycle status and clears
            `cancellation_requested_from`, then flushes the current database
            transaction. The caller remains responsible for committing or
            rolling back so resolution persistence stays atomic with its audit
            log. Payment confirmation and provider fulfillment trace fields are
            intentionally left untouched.
        """
        order.status = status.value
        order.cancellation_requested_from = None
        self.db.add(order)
        self.db.flush()
        return order
