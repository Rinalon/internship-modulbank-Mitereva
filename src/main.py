from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core import async_engine
from src.db.models import Base


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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
