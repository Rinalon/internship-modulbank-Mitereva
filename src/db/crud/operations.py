from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import OperationCreate, OperationUpdate
from src.db.models import Operation, Event
from src.core.exceptions import (
    OperationExistsError,
    OperationNotFoundError,
    PaymentIdAlreadySetError
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
    new_event = Event(operationId=operationId, message="")

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
