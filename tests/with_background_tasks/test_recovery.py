import pytest
import asyncio
import httpx
from uuid import uuid4
from unittest.mock import patch

from src.db.crud import create_operation, get_operation, update_operation
from src.db.schemas import OperationCreate, OperationUpdate
from src.core import OperationStates, settings
from src.services.provider import reset_query

from conftest import TestAsyncSessionLocal

@pytest.mark.background
@pytest.mark.asyncio
async def test_recovery_after_restart(session):
    data = OperationCreate(
        operationId="test-recovery",
        amount="200.00",
        currency="RUB",
        description="Recovery test",
    )
    await create_operation(session, data)

    # Переводим в PROCESSING
    await update_operation(session, "test-recovery", OperationUpdate(status=OperationStates.processing))

    provider_id = str(uuid4())
    mock_response = httpx.Response(
        202,
        json={"providerPaymentId": provider_id, "status": "ACCEPTED"},
    )

    with patch("src.core.AsyncSessionLocal", TestAsyncSessionLocal):
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
                # Имитируем запуск сервиса – вызываем функцию восстановления, как в lifespan
            tasks = await reset_query(session)

            if tasks:
                await asyncio.gather(*tasks)

            mock_post.assert_called_once()

            # Проверяем URL и тело запроса
            call_args = mock_post.call_args
            assert call_args[0][0] == f"{settings.PROVIDER_URL}/payments"
            assert call_args[1]["json"]["operationId"] == "test-recovery"
            assert call_args[1]["json"]["amount"] == "200.00"
            assert call_args[1]["json"]["currency"] == "RUB"

            # Проверяем заголовки идемпотентности
            headers = call_args[1]["headers"]
            assert headers["Idempotency-Key"] == "test-recovery"
            assert headers["X-Correlation-ID"] == "test-recovery"

    # Проверяем сохранения в БД
    op = await get_operation(session, "test-recovery")
    assert str(op.providerPaymentId) == provider_id
    assert op.status == OperationStates.processing