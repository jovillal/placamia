from enum import StrEnum


class ProviderDeliveryEvent(StrEnum):
    """Backend-owned provider delivery events."""

    DELIVERY_CONFIRMED = "delivery_confirmed"
