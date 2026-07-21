import pytest
import httpx
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timezone

from src.db.crud import create_operation, get_operation, update_operation
from src.db.schemas import OperationCreate, OperationUpdate, ReceiptData
from src.core import OperationStates
from src.core.exceptions import ProviderUnavailableError, ProviderError
from src.services.provider import send_to_provider

@pytest.mark.asyncio
async def test_provider_503_retry(session):
    data = OperationCreate(
        operationId="test-provider-503",
        amount="300.00",
        currency="RUB",
        description="503 test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-provider-503", OperationUpdate(status=OperationStates.processing))

    mock_responses = [
        httpx.Response(503, json={"error": "Service Unavailable"}),
        httpx.Response(202, json={"providerPaymentId": str(uuid4()), "status": "ACCEPTED"}),
    ]
    with patch.object(httpx.AsyncClient, 'post', side_effect=mock_responses) as mock_post:
        result = await send_to_provider("test-provider-503", "300.00")
        assert result is not None
        assert mock_post.call_count == 2
        # проверка, что в БД сохранился providerPaymentId
        op = await get_operation(session, "test-provider-503")
        assert str(op.providerPaymentId) == result


@pytest.mark.asyncio
async def test_provider_timeout(session):
    data = OperationCreate(
        operationId="test-provider-timeout",
        amount="400.00",
        currency="RUB",
        description="Timeout test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-provider-timeout", OperationUpdate(status=OperationStates.processing))

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")) as mock_post:
        with pytest.raises(ProviderUnavailableError):
            await send_to_provider("test-provider-timeout", "400.00")

        assert mock_post.call_count >= 2

    op = await get_operation(session, "test-provider-timeout")
    assert op.status == OperationStates.processing


@pytest.mark.asyncio
async def test_provider_network_error(session):
    data = OperationCreate(
        operationId="test-provider-network",
        amount="500.00",
        currency="RUB",
        description="Network error test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-provider-network", OperationUpdate(status=OperationStates.processing))

    # Мок сетевой ошибки
    with patch("httpx.AsyncClient.post", side_effect=httpx.NetworkError("Network unreachable")) as mock_post:
        with pytest.raises(ProviderUnavailableError):
            await send_to_provider("test-provider-network", "500.00")

        assert mock_post.call_count >= 2

    op = await get_operation(session, "test-provider-network")
    assert op.status == OperationStates.processing


@pytest.mark.asyncio
async def test_provider_success_after_retry(session):
    data = OperationCreate(
        operationId="test-provider-retry-success",
        amount="600.00",
        currency="RUB",
        description="Retry success test",
    )
    await create_operation(session, data)
    await update_operation(session, "test-provider-retry-success", OperationUpdate(status=OperationStates.processing))

    provider_id = str(uuid4())

    # Сначала 503, потом успех
    mock_responses = [
        httpx.Response(503, json={"error": "Service Unavailable"}),
        httpx.Response(202, json={"providerPaymentId": provider_id, "status": "ACCEPTED"}),
    ]

    with patch("httpx.AsyncClient.post", side_effect=mock_responses) as mock_post:
        result = await send_to_provider("test-provider-retry-success", "600.00")
        assert result == provider_id
        assert mock_post.call_count == 2

    op = await get_operation(session, "test-provider-retry-success")
    assert str(op.providerPaymentId) == provider_id


@pytest.mark.asyncio
async def test_network_error_keeps_status_processing(session):
    data = OperationCreate(
        operationId="test-network-status",
        amount="700.00",
        currency="RUB",
        description="Status check",
    )
    await create_operation(session, data)
    await update_operation(session, "test-network-status", OperationUpdate(status=OperationStates.processing))

    with patch("httpx.AsyncClient.post", side_effect=httpx.NetworkError("Network error")):
        try:
            await send_to_provider.__wrapped__("test-network-status", "700.00")
        except ProviderUnavailableError:
            pass

    op = await get_operation(session, "test-network-status")
    assert op.status == OperationStates.processing
    assert op.providerPaymentId is None