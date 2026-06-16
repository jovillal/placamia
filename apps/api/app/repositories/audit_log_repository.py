from app.models.audit_log import AuditLog
from sqlalchemy import select
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

    def get_audit_logs_for_resource_action(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | int,
    ) -> list[AuditLog]:
        """Return audit logs for one resource/action pair.

        Args:
            action: Stable audit action name to match.
            resource_type: Domain resource type to match.
            resource_id: Domain resource identifier to match.

        Returns:
            Matching audit logs sorted oldest first.

        Side effects:
            None.
        """
        result = self.db.execute(
            select(AuditLog)
            .where(
                AuditLog.action == action,
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == str(resource_id),
            )
            .order_by(AuditLog.id.asc())
        )
        return list(result.scalars().all())
