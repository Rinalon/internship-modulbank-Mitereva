from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import EventCreate
from src.db.models import Event
from src.db.crud.operations import get_operation
from src.core.exceptions import OperationNotFoundError

from datetime import datetime, timezone

async def get_events(session: AsyncSession,
                     operationId: str,
                     limit: int = 10,
                     offset: int = 0,
                     ) -> list[Event]:
    results = await session.execute(
        select(Event)
        .where(Event.operationId == operationId)
        .order_by(Event.eventId)
        .limit(limit)
        .offset(offset)
    )
    return list(results.scalars().all())

async def create_event(session: AsyncSession, event: EventCreate) -> Event:
    operationId = event.operationId
    operation = await get_operation(session, operationId)

    if operation is None:
        raise OperationNotFoundError(operationId)

    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event