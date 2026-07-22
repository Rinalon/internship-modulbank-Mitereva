from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import EventCreate
from src.db.models import Event
from src.db.crud.operation import get_operation
from src.core.exceptions import OperationNotFoundError

from datetime import datetime, timezone

async def get_events(session: AsyncSession, operationId: str) -> list[Event]:
    results = await session.execute(
        select(Event)
        .where(Event.operationId == operationId)
        .order_by(Event.eventId)
    )
    return list(results.scalars().all())

async def create_event(session: AsyncSession, event: EventCreate) -> Event:
    operationId = event.operationId
    operation = await get_operation(session, operationId)

    if operation is None:
        raise OperationNotFoundError(operationId)

    new_event = Event(
        operationId=operationId,
        type=event.type,
        providerPaymentId=event.providerPaymentId,
        fromStatus=event.fromStatus,
        toStatus=event.toStatus,
        message=event.message,
        occurredAt=event.occurredAt or datetime.now(timezone.utc),
    )
    session.add(new_event)

    await session.commit()
    await session.refresh(new_event)

    return new_event