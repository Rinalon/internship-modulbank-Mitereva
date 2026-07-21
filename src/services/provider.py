from src.db.schemas import OperationUpdate
from src.db.crud import update_operation, get_processing_operations
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.core.exceptions import ProviderUnavailableError, ProviderError
from src.core import settings, AsyncSessionLocal

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import asyncio
import httpx

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(ProviderUnavailableError),
    reraise=True
)
async def send_to_provider(operationId: str, amount: str, currency: str = "RUB"):
    url = f"{settings.PROVIDER_URL}/payments"
    headers = {
        "Idempotency-Key": operationId,
        "X-Correlation-ID": operationId,
        "Content-Type": "application/json",
    }
    body = {
        "operationId": operationId,
        "amount": amount,
        "currency": "RUB",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        raise ProviderUnavailableError()

    if response.status_code == 202:
        data = response.json()
        providerPaymentId = data.get("providerPaymentId")
        async with AsyncSessionLocal() as session:
            updData = OperationUpdate(providerPaymentId=providerPaymentId)
            await update_operation(session, operationId, updData)
        return providerPaymentId

    elif response.status_code == 503:
        raise ProviderUnavailableError()
    else:
        raise ProviderError(f"Unexpected status: {response.status_code}")

async def reset_query(session: AsyncSession):
    operations = await get_processing_operations(session)

    for operation in operations:
        asyncio.create_task(
            send_to_provider(
                operation.operationId,
                operation.amount
            )
        )