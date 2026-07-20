from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio.session import AsyncSession
import asyncio
from src.core.exceptions import (
    OperationExistsError,
    OperationNotFoundError
)
from src.core import get_db, OperationStates, EventTypes
from src.db.schemas import (
    OperationCreate,
    OperationUpdate,
    OperationResponse,
    EventCreate,
    EventResponse
)
from src.db.crud import (
    get_operation as read_operation,
    create_operation as make_operation,
    update_operation,
    get_events as read_events,
    create_event
)
from src.services import send_to_provider

router = APIRouter(prefix="/operations", tags=["operations"])

@router.get("/{id}", response_model=OperationResponse)
async def get_operation(id: str, session: AsyncSession = Depends(get_db)):
    operation = await read_operation(session, id)

    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    return operation

@router.get("/{id}/events", response_model=list[EventResponse])
async def get_events(id: str, session: AsyncSession = Depends(get_db)):
    try:
        events = await read_events(session, id)
        return events
    except OperationNotFoundError:
        raise HTTPException(status_code=404, detail="Operation not found")

@router.post("/", response_model=OperationResponse, status_code=201)
async def create_operation(operation_data: OperationCreate, session: AsyncSession = Depends(get_db)):
    try:
        new_operation = await make_operation(session, operation_data)

        return new_operation
    except OperationExistsError:
        raise HTTPException(status_code=409, detail="Operation already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{id}/submit", response_model=OperationResponse)
async def submit_operation(id: str,session: AsyncSession = Depends(get_db)):
    operation = await read_operation(session, id)

    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    if operation.status != OperationStates.created:
        response_data = OperationResponse.model_validate(operation)
        return JSONResponse(status_code=200, content=response_data.model_dump(mode='json'))

    changes = OperationUpdate(status=OperationStates.processing)
    event = EventCreate(
        type=EventTypes.processing,
        operationId=operation.operationId,
        fromStatus=operation.status,
        toStatus=OperationStates.processing,
        message=f"Change status from {operation.status} to {OperationStates.processing}"
    )
    await update_operation(session=session, updData=changes, operationId=id)
    await create_event(session=session, event=event)

    asyncio.create_task(send_to_provider(id, operation.amount))

    response_data = OperationResponse.model_validate(operation)
    return JSONResponse(status_code=202, content=response_data.model_dump(mode='json'))


