import pytest
from datetime import datetime, timezone
from src.db.crud import (
    create_operation,
    get_operation,
    get_processing_operations,
    update_operation,
    process_receipt,
    create_event
)
from src.db.schemas import (
    OperationCreate,
    OperationUpdate,
    ReceiptData,
    EventCreate,
)
from src.core import OperationStates, EventTypes, ReceiptResultTypes
from src.core.exceptions import (
    OperationExistsError,
    OperationNotFoundError,
    PaymentIdAlreadySetError,
    PaymentIdMissmatchError,
    StatusUnmatchedError,
)
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_operation_success(session):
    data = OperationCreate(
        operationId="test-1",
        amount="100.00",
        currency="RUB",
        description="Test operation",
    )
    op = await create_operation(session, data)
    assert op.operationId == "test-1"
    assert op.status == OperationStates.created
    assert op.amount == "100.00"

    # Проверяем, что событие создано
    from src.db.crud.event import get_events
    events = await get_events(session, "test-1")
    assert len(events) == 1
    assert events[0].type == EventTypes.created

@pytest.mark.asyncio
async def test_create_operation_duplicate(session):
    data = OperationCreate(
        operationId="test-dup",
        amount="50.00",
        currency="RUB",
        description="Duplicate",
    )
    await create_operation(session, data)

    with pytest.raises(OperationExistsError):
        await create_operation(session, data)

@pytest.mark.asyncio
async def test_get_operation_success(session):
    data = OperationCreate(
        operationId="test-get",
        amount="200.00",
        currency="RUB",
        description="Get test",
    )
    await create_operation(session, data)
    op = await get_operation(session, "test-get")
    assert op is not None
    assert op.operationId == "test-get"

@pytest.mark.asyncio
async def test_get_operation_not_found(session):
    op = await get_operation(session, "nonexistent")
    assert op is None

@pytest.mark.asyncio
async def test_update_operation_status(session):
    data = OperationCreate(
        operationId="test-upd",
        amount="300.00",
        currency="RUB",
        description="Update status",
    )
    await create_operation(session, data)

    update = OperationUpdate(status=OperationStates.processing)
    await update_operation(session, "test-upd", update)

    op = await get_operation(session, "test-upd")
    assert op.status == OperationStates.processing

    # Проверяем, что событие создано
    from src.db.crud.event import get_events
    events = await get_events(session, "test-upd")
    # должно быть два события: CREATED и PROCESSING
    assert len(events) == 2
    assert events[1].type == EventTypes.processing

@pytest.mark.asyncio
async def test_update_operation_invalid_status(session):
    data = OperationCreate(
        operationId="test-inv",
        amount="400.00",
        currency="RUB",
        description="Invalid status",
    )
    await create_operation(session, data)

    # Пытаемся изменить CREATED сразу на COMPLETED (не разрешено)
    update = OperationUpdate(status=OperationStates.completed)
    with pytest.raises(StatusUnmatchedError):
        await update_operation(session, "test-inv", update)

@pytest.mark.asyncio
async def test_update_operation_provider_payment_id(session):
    data = OperationCreate(
        operationId="test-provider",
        amount="500.00",
        currency="RUB",
        description="Provider id",
    )
    await create_operation(session, data)

    provider_id = uuid4()
    update = OperationUpdate(providerPaymentId=provider_id)
    await update_operation(session, "test-provider", update)

    op = await get_operation(session, "test-provider")
    assert op.providerPaymentId == provider_id

    # Повторная установка того же ID не должна вызвать ошибку (если уже установлен)
    # Но если другой ID, то ошибка
    with pytest.raises(PaymentIdAlreadySetError):
        await update_operation(session, "test-provider", OperationUpdate(providerPaymentId=uuid4()))

@pytest.mark.asyncio
async def test_process_receipt_success(session):
    # Создаём операцию и переводим в PROCESSING
    data = OperationCreate(
        operationId="test-receipt",
        amount="600.00",
        currency="RUB",
        description="Receipt test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-receipt", OperationUpdate(status=OperationStates.processing))

    receipt = ReceiptData(
        operationId="test-receipt",
        providerPaymentId=uuid4(),
        result=ReceiptResultTypes.completed,
        message="Payment completed",
        occurredAt=datetime.now(timezone.utc),
    )
    await process_receipt(session, receipt)

    op = await get_operation(session, "test-receipt")
    assert op.status == OperationStates.completed
    assert op.providerPaymentId == receipt.providerPaymentId

    # Проверяем события
    from src.db.crud.event import get_events
    events = await get_events(session, "test-receipt")
    types = [e.type for e in events]
    assert EventTypes.provider_response in types
    assert EventTypes.completed in types

@pytest.mark.asyncio
async def test_process_receipt_already_completed(session):
    # Создаём операцию и завершаем её
    data = OperationCreate(
        operationId="test-completed",
        amount="700.00",
        currency="RUB",
        description="Already completed",
    )
    await create_operation(session, data)
    await update_operation(session, "test-completed", OperationUpdate(status=OperationStates.processing))
    # Первая квитанция
    receipt1 = ReceiptData(
        operationId="test-completed",
        providerPaymentId=uuid4(),
        result=ReceiptResultTypes.completed,
        message="Completed",
        occurredAt=datetime.now(timezone.utc),
    )
    await process_receipt(session, receipt1)

    # Вторая квитанция (другой ID)
    receipt2 = ReceiptData(
        operationId="test-completed",
        providerPaymentId=uuid4(),
        result=ReceiptResultTypes.completed,
        message="Another receipt",
        occurredAt=datetime.now(timezone.utc),
    )
    await process_receipt(session, receipt2)

    op = await get_operation(session, "test-completed")
    assert op.status == OperationStates.completed
    assert op.providerPaymentId == receipt1.providerPaymentId  # не изменился

    # Проверяем события игнорирования
    from src.db.crud.event import get_events
    events = await get_events(session, "test-completed")
    ignored = [e for e in events if e.type == EventTypes.receipt_ignored]
    assert len(ignored) == 1

@pytest.mark.asyncio
async def test_process_receipt_mismatch_provider_id(session):
    data = OperationCreate(
        operationId="test-mismatch",
        amount="800.00",
        currency="RUB",
        description="Mismatch",
    )
    await create_operation(session, data)
    await update_operation(session, "test-mismatch", OperationUpdate(status=OperationStates.processing))

    # Устанавливаем один providerPaymentId
    pid1 = uuid4()
    await update_operation(session, "test-mismatch", OperationUpdate(providerPaymentId=pid1))

    # Приходит квитанция с другим ID
    receipt = ReceiptData(
        operationId="test-mismatch",
        providerPaymentId=uuid4(),
        result=ReceiptResultTypes.completed,
        message="Mismatch",
        occurredAt=datetime.now(timezone.utc),
    )
    with pytest.raises(PaymentIdMissmatchError):
        await process_receipt(session, receipt)

@pytest.mark.asyncio
async def test_get_processing_operations(session):
    data1 = OperationCreate(operationId="proc-1", amount="10.00", currency="RUB", description="")
    await create_operation(session, data1)
    await update_operation(session, "proc-1", OperationUpdate(status=OperationStates.processing))

    data2 = OperationCreate(operationId="proc-2", amount="20.00", currency="RUB", description="")
    await create_operation(session, data2)

    procs = await get_processing_operations(session)
    assert len(procs) == 1
    assert procs[0].operationId == "proc-1"

@pytest.mark.asyncio
async def test_create_event_operation_not_found(session):
    event_data = EventCreate(
        type=EventTypes.created,
        operationId="nonexistent",
        fromStatus=None,
        toStatus=OperationStates.created,
        message="Should fail",
    )
    with pytest.raises(OperationNotFoundError):
        await create_event(session, event_data)