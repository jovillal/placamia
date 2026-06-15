from app.domain.provider_adapter import AcceptanceDecision
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
