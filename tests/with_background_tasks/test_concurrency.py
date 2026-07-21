import pytest
import asyncio

from src.db.crud.event import get_events
from src.core import EventTypes
from src.db.crud import (
    create_operation,
    get_operation,
    get_operation as read_op,
    update_operation,
)
from src.db.schemas import OperationCreate, OperationUpdate
from src.core import OperationStates, AsyncSessionLocal

@pytest.mark.background
@pytest.mark.asyncio
async def test_concurrent_submit_same_operation(session):
    data = OperationCreate(
        operationId="test-concurrent-submit",
        amount="100.00",
        currency="RUB",
        description="Concurrent submit test",
    )
    await create_operation(session, data)

    # Имитация отдельного submit
    async def submit_in_session(operation_id: str):

        async with AsyncSessionLocal() as sess:
            changes = OperationUpdate(status=OperationStates.processing)
            updated = await update_operation(sess, operation_id, changes)
            updated_op = await read_op(sess, operation_id)
            return (updated_op.status, updated)

    tasks = [submit_in_session("test-concurrent-submit") for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # ровно один вызов должен изменить статус
    changed_count = sum(1 for _, changed in results if changed)
    assert changed_count == 1

    # Проверка статуса в БД
    op = await get_operation(session, "test-concurrent-submit")
    assert op.status == OperationStates.processing

    # Ровно 1 event о смене статуса
    events = await get_events(session, "test-concurrent-submit")
    processing_events = [e for e in events if e.type == EventTypes.processing]
    assert len(processing_events) == 1