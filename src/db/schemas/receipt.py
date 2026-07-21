from pydantic import BaseModel, ConfigDict
from uuid import UUID as PY_UUID
from datetime import datetime
from typing import Literal

class ReceiptData(BaseModel):
    operationId: str
    providerPaymentId: PY_UUID
    result: Literal["COMPLETED", "REJECTED"]
    message: str
    occurredAt: datetime

    model_config = ConfigDict(extra="allow")