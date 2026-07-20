from src.api.operations import router as operations_router
from src.api.receipts import router as receipts_router
from src.api.health import router as health_router
__all__ = [
    "operations_router",
    "receipts_router",
    "health_router",
]