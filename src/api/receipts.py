from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio.session import AsyncSession
from src.db.schemas import ReceiptData
from src.db.crud import  process_receipt
from src.core.exceptions import OperationNotFoundError, PaymentIdMissmatchError

from src.core import get_db


router = APIRouter(tags=["receipts"])
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