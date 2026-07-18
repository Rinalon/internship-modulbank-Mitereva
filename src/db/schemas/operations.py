from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from uuid import UUID as PY_UUID
from datetime import datetime
from typing import Optional, Literal
from src.db.models import OperationStates

class OperationCreate(BaseModel):
    operationId: str
    amount: str = Field(pattern=r"^\d+\.\d{0,2}$")
    currency: str = Literal["RUB"]
    description: Optional[str] = Field(None, max_length=255)

class OperationUpdate(BaseModel):
    status: Optional[OperationStates] = None
    providerPaymentId: Optional[PY_UUID] = None

class OperationResponse(BaseModel):
    operationId: str
    amount: str
    currency: str
    status: OperationStates
    providerPaymentId: Optional[PY_UUID] = None
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )