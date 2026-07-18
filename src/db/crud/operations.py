from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import OperationCreate, OperationUpdate
from src.db.models import Operation
from src.core.exceptions import (
    OperationExistsError,
    OperationNotFoundError,
    PaymentIdAlreadySetError
)
from src.core import OperationStates, validate_change_statuses
from src.core.exceptions import StatusUnmatchedError
from datetime import datetime, timezone

async def create_operation(session: AsyncSession, operationData: OperationCreate):
    operation = await get_operation(session, operationData.operationId)

    if operation is not None:
        raise OperationExistsError(operationData.operationId)

    operation = Operation(
        operationId=operationData.operationId,
        amount=operationData.amount,
        currency=operationData.currency,
        description=operationData.description,
        status=OperationStates.created,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    session.add(operation)
    await session.commit()
    await session.refresh(operation)
    return operation

async def get_operation(session: AsyncSession, operationId: str) -> Operation | None:
    result = await session.execute(
        select(Operation)
        .where(Operation.operationId == operationId)
    )
    return result.scalar_one_or_none()

async def get_operation_for_update(session: AsyncSession, operation_id: str) -> Operation | None:
    result = await session.execute(
        select(Operation)
        .where(Operation.operationId == operation_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()

async def update_operation(session: AsyncSession, operationId: str, updData: OperationUpdate) -> None:
    operation = await get_operation_for_update(session, operationId)
    if operation is None:
        raise OperationNotFoundError(operationId),

    updated = False

    if updData.status is not None:
        if validate_change_statuses(operation.status, updData.status):
            operation.status = updData.status
            updated = True
        else:
            raise StatusUnmatchedError(operationId, operation.status, updData.status),

    if (updData.providerPaymentId is not None and
            operation.providerPaymentId is None):
        operation.providerPaymentId = updData.providerPaymentId
        updated = True

    elif (updData.providerPaymentId is not None and
          operation.providerPaymentId is not None):
        raise PaymentIdAlreadySetError(operationId)

    if updated:
        operation.updatedAt = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(operation)
