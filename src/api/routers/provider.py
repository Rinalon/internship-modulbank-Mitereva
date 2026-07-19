from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import OperationUpdate, ReceiptData, EventCreate
from src.db.crud import update_operation, process_receipt
from src.core.exceptions import (
    ProviderUnavailableError,
    ProviderError,
    OperationNotFoundError,
    PaymentIdMissmatchError
)
from src.core import settings, AsyncSessionLocal, get_db, EventTypes
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import httpx


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
            ProviderUnavailableError,
            httpx.TimeoutException,
            httpx.NetworkError,
    )),
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=body, headers=headers)

    if response.status_code == 202:
        data = response.json()
        providerPaymentId = data.get("providerPaymentId")

        async with AsyncSessionLocal() as session:
            updData = OperationUpdate(providerPaymentId=providerPaymentId)
            await update_operation(session, operationId, updData)

    elif response.status_code == 503:
        raise ProviderUnavailableError()
    else:
        raise ProviderError(f"Unexpected status: {response.status_code}")


router = APIRouter(tags=["provider"])
@router.post("/receipts", status_code=204)
async def handle_receipt(data: ReceiptData, session: AsyncSession = Depends(get_db)):
    try:
        await process_receipt(session, data)
        await session.commit()
    except OperationNotFoundError:
        raise HTTPException(404, "Operation not found")
    except PaymentIdMissmatchError:
        raise HTTPException(409, "ProviderPaymentId mismatch")
    return