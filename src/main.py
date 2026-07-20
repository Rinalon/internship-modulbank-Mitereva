from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from src.core import async_engine, AsyncSessionLocal
from src.db.models import Base
from src.services import reset_query
from src.api import *
import uvicorn

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield
    await async_engine.dispose()

app = FastAPI(
    title="Payment Operations Service",
    description="Service for processing payment operations",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(operations_router)
app.include_router(receipts_router)
app.include_router(health_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )