from sqlalchemy import select, update
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette import status

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

async def update_operation(session: AsyncSession, operationId: str, updData: OperationUpdate) -> bool:
    operation = await get_operation_for_update(session, operationId)
    if operation is None:
        raise OperationNotFoundError(operationId)

    updated = False
    new_event = Event(
        operationId=operationId,
        fromStatus=operation.status,
        message=""
    )

    if updData.status is not None:
        if operation.status != updData.status:
            if not validate_change_statuses(operation.status, updData.status):
                raise StatusUnmatchedError(operationId, operation.status, updData.status)

            old_status = operation.status
            stmt = (
                update(Operation)
                .where(Operation.operationId == operationId)
                .where(Operation.status == old_status)
                .values(status=updData.status, updatedAt=datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)

            if result.rowcount > 0:
                updated = True
                operation.status = updData.status

                new_event.type = EventTypes.processing
                new_event.toStatus = updData.status
                new_event.message += f"Change status from {old_status} to {updData.status}."

            else:
                await session.refresh(operation)

    if updData.providerPaymentId is not None:
        if operation.providerPaymentId is None:
            operation.providerPaymentId = updData.providerPaymentId
            operation.updatedAt = datetime.now(timezone.utc)

            updated = True
            new_event.type = EventTypes.provider_response
            new_event.providerPaymentId = updData.providerPaymentId
            new_event.toStatus = updData.status or operation.status
            new_event.message += "Added provider payment id."



        elif operation.providerPaymentId != updData.providerPaymentId:
            raise PaymentIdAlreadySetError(operationId)

    if updated:
        new_event.occurredAt=datetime.now(timezone.utc)
        session.add(new_event)
        await session.commit()
        await session.refresh(operation)

    return updated

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
