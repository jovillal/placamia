from app.domain.provider_adapter import AcceptanceDecision
from app.domain.provider_delivery import ProviderDeliveryEvent
from app.domain.provider_production_progress import ProviderProductionProgressEvent
from app.domain.provider_shipment import ProviderShipmentEvent
from pydantic import BaseModel, ConfigDict


class ProviderAcceptanceDecisionRequest(BaseModel):
    """Request schema for backend-owned provider acceptance decisions."""

    decision: AcceptanceDecision

    model_config = ConfigDict(extra="forbid")


class ProviderAcceptanceDecisionResponse(BaseModel):
    """Customer-safe response after recording a provider decision."""

    order_id: int
    order_status: str
    provider_decision: AcceptanceDecision
    customer_safe_status: str
    customer_safe_reason_code: str | None = None
    idempotent: bool


class ProviderProductionProgressRequest(BaseModel):
    """Request schema for backend-owned production progress events."""

    event: ProviderProductionProgressEvent
    event_reference: str | None = None

    model_config = ConfigDict(extra="forbid")


class ProviderProductionProgressResponse(BaseModel):
    """Customer-safe response after recording production progress."""

    order_id: int
    order_status: str
    production_event: ProviderProductionProgressEvent
    customer_safe_status: str
    event_reference: str | None = None
    idempotent: bool


class ProviderShipmentRequest(BaseModel):
    """Request schema for backend-owned shipment events."""

    event: ProviderShipmentEvent
    event_reference: str | None = None

    model_config = ConfigDict(extra="forbid")


class ProviderShipmentResponse(BaseModel):
    """Customer-safe response after recording shipment."""

    order_id: int
    order_status: str
    shipment_event: ProviderShipmentEvent
    customer_safe_status: str
    event_reference: str | None = None
    idempotent: bool


class ProviderDeliveryRequest(BaseModel):
    """Request schema for backend-owned delivery confirmation events."""

    event: ProviderDeliveryEvent
    event_reference: str | None = None

    model_config = ConfigDict(extra="forbid")


class ProviderDeliveryResponse(BaseModel):
    """Customer-safe response after recording delivery confirmation."""

    order_id: int
    order_status: str
    delivery_event: ProviderDeliveryEvent
    customer_safe_status: str
    event_reference: str | None = None
    idempotent: bool
