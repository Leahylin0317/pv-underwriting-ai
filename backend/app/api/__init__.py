from .ocr_routes import router as ocr_router
from .routes import router
from .schemas import MockAnalyzeRequest

__all__ = [
    "MockAnalyzeRequest",
    "ocr_router",
    "router",
]
