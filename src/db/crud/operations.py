from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import OperationCreate, OperationUpdate, ReceiptData
from src.db.models import Operation, Event
from src.core.exceptions import (
    OperationExistsError,
    OperationNotFoundError,
    PaymentIdAlreadySetError,
    PaymentIdMissmatchError,
)
from src.core import OperationStates, validate_change_statuses, EventTypes
from src.core.exceptions import StatusUnmatchedError
from datetime import datetime, timezone

async def create_operation(session: AsyncSession, operationData: OperationCreate):
    operation = await get_operation(session, operationData.operationId)

    if operation is not None:
        raise OperationExistsError(operationData.operationId)

    new_operation = Operation(
        operationId=operationData.operationId,
        amount=operationData.amount,
        currency=operationData.currency,
        description=operationData.description,
        status=OperationStates.created,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    session.add(new_operation)

    new_event = Event(
        operationId=new_operation.operationId,
        type=EventTypes.created,
        fromStatus=None,
        toStatus=OperationStates.created,
        message="Operation created",
        occurredAt=datetime.now(timezone.utc),
    )
    session.add(new_event)

    await session.commit()
    await session.refresh(new_operation)
    return new_operation

async def get_operation(session: AsyncSession, operationId: str) -> Operation | None:
    result = await session.execute(
        select(Operation)
        .where(Operation.operationId == operationId)
    )
    return result.scalar_one_or_none()

async def get_operation_for_update(session: AsyncSession, operationId: str) -> Operation | None:
    result = await session.execute(
        select(Operation)
        .where(Operation.operationId == operationId)
        .with_for_update()
    )
    return result.scalar_one_or_none()

async def get_status(session: AsyncSession, operationId: str) -> OperationStates | None:
    result = await session.execute(
        select(Operation)
        .where(Operation.operationId == operationId))

    result = result.scalar_one_or_none()

    if result is None:
        raise OperationNotFoundError(operationId)

    return result.status

async def get_processing_operations(session: AsyncSession) -> list[Operation]:
    results = await session.execute(
        select(Operation)
        .where(Operation.status == OperationStates.processing)
    )
    return list(results.scalars().all())

async def update_operation(session: AsyncSession, operationId: str, updData: OperationUpdate) -> None:
    operation = await get_operation_for_update(session, operationId)
    if operation is None:
        raise OperationNotFoundError(operationId),

    updated = False
    new_event = Event(type=EventTypes.processing, operationId=operationId, message="")

    if updData.status is not None:
        if validate_change_statuses(operation.status, updData.status):
            operation.status = updData.status

            updated = True
            new_event.status = updData.status
            new_event.message += f"Change status from {operation.status} to {updData.status}. "
        else:
            raise StatusUnmatchedError(operationId, operation.status, updData.status),

    if updData.providerPaymentId is not None:
        if operation.providerPaymentId is None:
            operation.providerPaymentId = updData.providerPaymentId

            updated = True
            new_event.providerPaymentId = updData.providerPaymentId
            new_event.message += "Added provider payment id."

        elif operation.providerPaymentId != updData.providerPaymentId:
            raise PaymentIdAlreadySetError(operationId)

    if updated:
        operation.updatedAt = datetime.now(timezone.utc)
        new_event.occurredAt = datetime.now(timezone.utc)

        session.add(new_event)
        await session.commit()
        await session.refresh(operation)

async def process_receipt(session: AsyncSession, data: ReceiptData):
    operationId = data.operationId
    operation = await get_operation_for_update(session, operationId)

    if operation is None:
        raise OperationNotFoundError(operationId)

    if (operation.providerPaymentId is not None and
            operation.providerPaymentId != data.providerPaymentId):
        raise PaymentIdMissmatchError(operationId)

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

    if data.result == OperationStates.completed:
        updType = EventTypes.completed
    else:
        updType = EventTypes.rejected

    updated_event = Event(
        type=updType,
        operationId=operationId,
        fromStatus=operation.status,
        toStatus=data.result,
        message=f"Status changed to {data.result} via receipt",
        occurredAt=datetime.now(timezone.utc),
    )

    if operation.providerPaymentId is None:
        operation.providerPaymentId = data.providerPaymentId

    operation.status = data.result
    operation.updatedAt = datetime.now(timezone.utc)

    session.add(updated_event)
    await session.commit()
