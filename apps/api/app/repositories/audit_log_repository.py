from app.models.audit_log import AuditLog
from sqlalchemy.orm import Session


class AuditLogRepository:
    """Database access for administrative audit logs.

    The repository centralizes audit log persistence so services can record
    security-relevant admin events without depending on SQLAlchemy directly.
    """

    def __init__(self, db: Session) -> None:
        """Create an audit log repository bound to a database session.

        Args:
            db: SQLAlchemy session used for audit log writes.

        Returns:
            None.

        Side effects:
            Stores the session for subsequent write operations.
        """
        self.db = db

    def create_audit_log(self, audit_log: AuditLog) -> AuditLog:
        """Persist an audit log record and flush it to assign an id.

        Args:
            audit_log: Audit log model instance to persist.

        Returns:
            The persisted audit log model instance.

        Side effects:
            Adds the audit log to the current database transaction and flushes
            the session. The caller remains responsible for committing or
            rolling back the transaction.
        """
        self.db.add(audit_log)
        self.db.flush()
        return audit_log
