from enum import StrEnum


class ProviderProductionProgressEvent(StrEnum):
    """Backend-owned provider production progress events."""

    PRODUCTION_STARTED = "production_started"
    PACKAGE_READY_FOR_PICKUP = "package_ready_for_pickup"
