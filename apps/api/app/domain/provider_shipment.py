from enum import StrEnum


class ProviderShipmentEvent(StrEnum):
    """Backend-owned provider shipment events."""

    CARRIER_QR_PICKUP_SCAN = "carrier_qr_pickup_scan"
    AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK = "authorized_operator_shipment_fallback"
