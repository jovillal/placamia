from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.products import router as products_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(health_router)
router.include_router(products_router)
