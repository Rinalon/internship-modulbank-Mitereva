from fastapi import APIRouter, Depends, HTTPException
from src.db.schemas import OperationUpdate

router = APIRouter(tags=["provider"])

async def send_to_provider(operation_id: str):
    pass

@router.post("/receipts")
async def handle_receipt(data: OperationUpdate):
    pass