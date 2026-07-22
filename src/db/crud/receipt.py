from sqlalchemy.ext.asyncio.session import AsyncSession

from src.db.schemas import ReceiptData
from src.db.models import Event
from src.core.exceptions import OperationNotFoundError, PaymentIdMissmatchError

from src.core import OperationStates, EventTypes
from datetime import datetime, timezone
from src.db.crud.operation import get_operation_for_update

async def process_receipt(session: AsyncSession, data: ReceiptData):
    operationId = data.operationId
    operation = await get_operation_for_update(session, operationId)

    if operation is None:
        raise OperationNotFoundError(operationId)

    if operation.status in (OperationStates.completed, OperationStates.rejected):
        ignore_event = Event(
            type=EventTypes.receipt_ignored,
            operationId=operationId,
            fromStatus=operation.status,
            toStatus=operation.status,
            message=f"Ignored receipt for already completed operation",
            occurredAt=data.occurredAt,
        )
        session.add(ignore_event)
        await session.commit()
        return
    if (operation.providerPaymentId is not None and
            operation.providerPaymentId != data.providerPaymentId):
        raise PaymentIdMissmatchError(operationId)

    provider_event = Event(
        type=EventTypes.provider_response,
        operationId=operationId,
        providerPaymentId=data.providerPaymentId,
        fromStatus=operation.status,
        toStatus=operation.status,
        message=data.message,
        occurredAt=data.occurredAt
    )
    session.add(provider_event)

    if data.result == "COMPLETED":
        updType = EventTypes.completed
        status = OperationStates.completed
    else:
        updType = EventTypes.rejected
        status = OperationStates.rejected

    updated_event = Event(
        type=updType,
        operationId=operationId,
        fromStatus=operation.status,
        toStatus=status,
        message=f"Status changed to {data.result} via receipt",
        occurredAt=datetime.now(timezone.utc),
    )

    if operation.providerPaymentId is None:
        operation.providerPaymentId = data.providerPaymentId

    operation.status = status
    operation.updatedAt = datetime.now(timezone.utc)

    session.add(updated_event)
    await session.commit()
