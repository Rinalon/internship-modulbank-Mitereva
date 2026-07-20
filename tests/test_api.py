import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.core.database import get_db
from src.db.schemas import OperationCreate, OperationUpdate
from src.db.crud import create_operation, get_operation, update_operation
from src.core import OperationStates
from datetime import datetime, timezone
from uuid import uuid4


@pytest.fixture
async def client(session):
    """Асинхронный клиент FastAPI с переопределённой зависимостью get_db."""
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_operation_success(client, session):
    data = {
        "operationId": "test-api-1",
        "amount": "100.00",
        "currency": "RUB",
        "description": "Test API",
    }
    response = await client.post("/operations/", json=data)
    assert response.status_code == 201
    body = response.json()
    assert body["operationId"] == "test-api-1"
    assert body["status"] == "CREATED"
    assert body["providerPaymentId"] is None


@pytest.mark.asyncio
async def test_create_operation_conflict(client, session):
    data = {
        "operationId": "test-api-conflict",
        "amount": "50.00",
        "currency": "RUB",
        "description": "Conflict",
    }
    # Первое создание
    await client.post("/operations/", json=data)
    # Повторное создание
    response = await client.post("/operations/", json=data)
    assert response.status_code == 409
    assert "already exists" in response.text


@pytest.mark.asyncio
async def test_get_operation_success(client, session):
    data = OperationCreate(
        operationId="test-api-get",
        amount="200.00",
        currency="RUB",
        description="Get test",
    )
    await create_operation(session, data)

    response = await client.get("/operations/test-api-get")
    assert response.status_code == 200
    body = response.json()
    assert body["operationId"] == "test-api-get"
    assert body["status"] == "CREATED"


@pytest.mark.asyncio
async def test_get_operation_not_found(client):
    response = await client.get("/operations/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_operation_created(client, session):
    # Создаём операцию
    data = OperationCreate(
        operationId="test-api-submit",
        amount="300.00",
        currency="RUB",
        description="Submit test",
    )
    await create_operation(session, data)

    # Мокаем send_to_provider, чтобы не делать реальный запрос
    with patch("src.services.send_to_provider", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = None
        response = await client.post("/operations/test-api-submit/submit")
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "PROCESSING"

        # Проверяем, что send_to_provider вызван
        mock_send.assert_called_once_with("test-api-submit", "300.00")

        # Проверяем, что статус обновился в БД
        op = await get_operation(session, "test-api-submit")
        assert op.status == OperationStates.processing


@pytest.mark.asyncio
async def test_submit_operation_not_created(client, session):
    # Создаём операцию и сразу переводим в PROCESSING (имитируем submit)
    data = OperationCreate(
        operationId="test-api-already",
        amount="400.00",
        currency="RUB",
        description="Already processing",
    )
    await create_operation(session, data)
    await update_operation(session, "test-api-already", OperationUpdate(status=OperationStates.processing))

    response = await client.post("/operations/test-api-already/submit")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_submit_operation_not_found(client):
    response = await client.post("/operations/nonexistent/submit")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_events(client, session):
    # Создаём операцию (автоматически создаётся событие CREATED)
    data = OperationCreate(
        operationId="test-api-events",
        amount="500.00",
        currency="RUB",
        description="Events test",
    )
    await create_operation(session, data)

    # Делаем submit, чтобы добавить событие PROCESSING
    # Но для этого нужно обновить статус и создать событие вручную (или вызвать submit)
    # Так как submit вызывает внешний вызов, мы можем просто обновить статус и создать событие через CRUD
    await update_operation(session, "test-api-events", OperationUpdate(status=OperationStates.processing))

    response = await client.get("/operations/test-api-events/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2  # CREATED и PROCESSING
    assert events[0]["type"] == "CREATED"
    assert events[1]["type"] == "PROCESSING"


@pytest.mark.asyncio
async def test_receipt_success(client, session):
    # Подготовка: создаём операцию и переводим в PROCESSING
    data = OperationCreate(
        operationId="test-api-receipt",
        amount="600.00",
        currency="RUB",
        description="Receipt test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-api-receipt", OperationUpdate(status=OperationStates.processing))

    receipt_data = {
        "operationId": "test-api-receipt",
        "providerPaymentId": str(uuid4()),
        "result": "COMPLETED",
        "message": "Payment completed",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    response = await client.post("/receipts", json=receipt_data)
    assert response.status_code == 204

    # Проверяем, что статус изменился
    op = await get_operation(session, "test-api-receipt")
    assert op.status == OperationStates.completed
    assert op.providerPaymentId is not None


@pytest.mark.asyncio
async def test_receipt_already_completed(client, session):
    # Создаём и завершаем операцию
    data = OperationCreate(
        operationId="test-api-completed",
        amount="700.00",
        currency="RUB",
        description="Already completed",
    )
    await create_operation(session, data)
    await update_operation(session, "test-api-completed", OperationUpdate(status=OperationStates.processing))

    first_receipt = {
        "operationId": "test-api-completed",
        "providerPaymentId": str(uuid4()),
        "result": "COMPLETED",
        "message": "Completed",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    await client.post("/receipts", json=first_receipt)

    # Вторая квитанция (другой ID) должна проигнорироваться
    second_receipt = {
        "operationId": "test-api-completed",
        "providerPaymentId": str(uuid4()),
        "result": "COMPLETED",
        "message": "Another receipt",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    response = await client.post("/receipts", json=second_receipt)
    assert response.status_code == 204

    # Проверяем, что providerPaymentId не изменился
    op = await get_operation(session, "test-api-completed")
    assert op.providerPaymentId == first_receipt["providerPaymentId"]


@pytest.mark.asyncio
async def test_receipt_mismatch(client, session):
    # Создаём операцию и переводим в PROCESSING
    data = OperationCreate(
        operationId="test-api-mismatch",
        amount="800.00",
        currency="RUB",
        description="Mismatch",
    )
    await create_operation(session, data)
    await update_operation(session, "test-api-mismatch", OperationUpdate(status=OperationStates.processing))

    # Устанавливаем providerPaymentId
    pid1 = uuid4()
    await update_operation(session, "test-api-mismatch", OperationUpdate(providerPaymentId=pid1))

    # Приходит квитанция с другим ID
    receipt_data = {
        "operationId": "test-api-mismatch",
        "providerPaymentId": str(uuid4()),
        "result": "COMPLETED",
        "message": "Mismatch",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    response = await client.post("/receipts", json=receipt_data)
    assert response.status_code == 409
    assert "mismatch" in response.text.lower()