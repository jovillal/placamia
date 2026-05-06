from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kit import Kit


class KitRepository:
    """Data access layer for curated catalog kits.

    The repository receives a SQLAlchemy session and reads Kit records for
    catalog browsing without applying pricing, discount, checkout, or admin
    behavior.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by kit queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def get_active_kits(self) -> list[Kit]:
        """Return active kits ordered by name.

        Returns:
            A list of active Kit model instances sorted alphabetically.
        """
        result = self.db.execute(
            select(Kit).where(Kit.is_active.is_(True)).order_by(Kit.name)
        )
        return list(result.scalars().all())
