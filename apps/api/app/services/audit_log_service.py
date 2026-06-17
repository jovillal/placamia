from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Mapping

from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository

SENSITIVE_AUDIT_DETAIL_KEYS = (
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "card",
    "payment_card",
    "jwt",
    "refresh_token",
    "access_token",
    "api_key",
    "private_key",
    "environment",
)


class AuditLogService:
    """Record security-relevant audit actions.

    The service prepares audit event context, redacts obviously sensitive
    values, and delegates persistence to the repository layer. It does not
    commit the database transaction so callers can keep audit logs atomic with
    the business change being performed.
    """

    def __init__(self, audit_log_repository: AuditLogRepository) -> None:
        """Create an audit log service.

        Args:
            audit_log_repository: Repository used to persist audit log records.

        Returns:
            None.

        Side effects:
            Stores the repository for subsequent audit log writes.
        """
        self.audit_log_repository = audit_log_repository

    def record_admin_action(
        self,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str | int | None = None,
        event_details: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        """Record an auditable administrative action.

        Args:
            actor: Authenticated backend user performing the admin action.
            action: Stable action name, such as `product.update`.
            resource_type: Domain resource affected by the action.
            resource_id: Optional identifier of the affected resource.
            event_details: Optional structured context for investigation.

        Returns:
            The persisted audit log record.

        Side effects:
            Adds an audit log row to the current database transaction and
            flushes the session through the repository.

        Raises:
            ValueError: If action or resource type is empty.
        """
        return self._record_action(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_details=event_details,
        )

    def record_user_action(
        self,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str | int | None = None,
        event_details: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        """Record an auditable customer or authenticated-user action.

        Args:
            actor: Authenticated backend user performing the action.
            action: Stable action name, such as `order.cancellation.request`.
            resource_type: Domain resource affected by the action.
            resource_id: Optional identifier of the affected resource.
            event_details: Optional structured context for investigation.

        Returns:
            The persisted audit log record.

        Side effects:
            Adds an audit log row to the current database transaction and
            flushes the session through the repository.

        Raises:
            ValueError: If action or resource type is empty.
        """
        return self._record_action(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_details=event_details,
        )

    def _record_action(
        self,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str | int | None = None,
        event_details: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        """Normalize and persist one audit action."""
        normalized_action = action.strip()
        normalized_resource_type = resource_type.strip()

        if not normalized_action:
            raise ValueError("Audit log action is required")

        if not normalized_resource_type:
            raise ValueError("Audit log resource type is required")

        audit_log = AuditLog(
            actor_user_id=actor.id,
            action=normalized_action,
            resource_type=normalized_resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            event_details=self._redact_event_details(dict(event_details or {})),
        )

        return self.audit_log_repository.create_audit_log(audit_log)

    def _redact_event_details(self, value: Any) -> Any:
        """Return audit event details with sensitive values redacted.

        Args:
            value: Structured audit context value.

        Returns:
            A redacted copy of the provided value.

        Side effects:
            None.
        """
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if self._is_sensitive_key(key)
                    else self._redact_event_details(child_value)
                )
                for key, child_value in value.items()
            }

        if isinstance(value, list):
            return [self._redact_event_details(item) for item in value]

        if isinstance(value, str) and self._is_sensitive_value(value):
            return "[REDACTED]"

        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Return whether an audit detail key may contain sensitive data.

        Args:
            key: Audit detail key to inspect.

        Returns:
            True when the key name indicates sensitive data; otherwise False.

        Side effects:
            None.
        """
        normalized_key = key.lower()
        return any(
            sensitive_key in normalized_key
            for sensitive_key in SENSITIVE_AUDIT_DETAIL_KEYS
        )

    @classmethod
    def _is_sensitive_value(cls, value: str) -> bool:
        """Return whether a string value matches documented secret patterns.

        Args:
            value: Audit detail string value to inspect.

        Returns:
            True when the value matches an explicitly documented token or key
            pattern; otherwise False.

        Side effects:
            None.
        """
        return cls._is_jwt_like_value(value) or cls._is_pem_private_key_value(value)

    @staticmethod
    def _is_jwt_like_value(value: str) -> bool:
        """Return whether a value is a decodable JWT-shaped token."""
        parts = value.split(".")
        if len(parts) != 3 or any(not part for part in parts):
            return False

        try:
            padded_header = parts[0] + "=" * (-len(parts[0]) % 4)
            decoded_header = base64.urlsafe_b64decode(padded_header.encode("ascii"))
            header = json.loads(decoded_header.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return False

        return isinstance(header, dict) and (
            isinstance(header.get("alg"), str) or isinstance(header.get("typ"), str)
        )

    @staticmethod
    def _is_pem_private_key_value(value: str) -> bool:
        """Return whether a value contains a PEM private-key block marker."""
        normalized_value = value.upper()
        return (
            "-----BEGIN " in normalized_value
            and "PRIVATE KEY-----" in normalized_value
            and "-----END " in normalized_value
        )
