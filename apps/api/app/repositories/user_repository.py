from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Database access for application users.

    The repository centralizes user lookups so authentication dependencies do
    not query SQLAlchemy models directly.
    """

    def __init__(self, db: Session) -> None:
        """Create a user repository bound to a database session.

        Args:
            db: SQLAlchemy session used for user queries.

        Returns:
            None.

        Side effects:
            Stores the session for subsequent read operations.
        """
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        """Return a user by database identifier.

        Args:
            user_id: Database identifier from a verified authentication token.

        Returns:
            The matching user when found; otherwise `None`.

        Side effects:
            Reads from the database.
        """
        return self.db.get(User, user_id)
