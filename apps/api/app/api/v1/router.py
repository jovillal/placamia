from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.health import router as health_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(health_router)
