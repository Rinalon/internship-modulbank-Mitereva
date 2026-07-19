from pydantic import BaseModel, ConfigDict
from datetime import datetime
from src.core import OperationStates
from uuid import UUID as PY_UUID

class ReceiptData(BaseModel):
    operationId: str
    providerPaymentId: PY_UUID
    result: OperationStates
    message: str
    occurredAt: datetime

    model_config = ConfigDict(extra="allow")