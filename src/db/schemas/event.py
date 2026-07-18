from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator
)
from uuid import UUID as PY_UUID
from datetime import datetime
from typing import Optional
from src.core import OperationStates, EventTypes


class EventCreate(BaseModel):
    type: EventTypes
    operationId: str
    providerPaymentId: Optional[PY_UUID] = None
    fromStatus: Optional[OperationStates] = None
    toStatus: OperationStates
    message: str = Field(max_length=255)

class EventResponse(BaseModel):
    type: EventTypes
    operationId: str
    providerPaymentId: Optional[PY_UUID] = None
    fromStatus: Optional[OperationStates] = None
    toStatus: OperationStates
    message: str
    occurredAt: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )