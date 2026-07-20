from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)
from uuid import UUID as PY_UUID
from datetime import datetime
from typing import Optional, Literal
from src.core import OperationStates

class OperationCreate(BaseModel):
    operationId: str
    amount: str = Field(pattern=r"^\d+\.\d{0,2}$")
    currency: Literal["RUB"] = "RUB"
    description: Optional[str] = Field(None, max_length=255)

    @field_validator("currency", mode="before")
    @classmethod
    def upper_amount(cls, value):
        return value.upper()

    model_config = ConfigDict(extra="allow")


class OperationUpdate(BaseModel):
    status: Optional[OperationStates] = None
    providerPaymentId: Optional[PY_UUID] = None

class OperationResponse(BaseModel):
    operationId: str
    amount: str
    currency: Literal["RUB"] = "RUB"
    status: OperationStates
    providerPaymentId: Optional[PY_UUID] = None
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        use_enum_values=True
    )