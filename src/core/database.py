from src.core import settings
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

engine = create_engine(
    url=settings.database_url,
    echo=settings.DEBUG,
    #pool_size=5,
    #max_overflow=2
)


async_engine = create_async_engine(
    url=settings.database_url_async,
    echo=settings.DEBUG,
    #pool_size=5,
    #max_overflow=2
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Генератор сессий для внедрения в эндпоинты FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session
