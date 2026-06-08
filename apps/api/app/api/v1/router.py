from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.kits import router as kits_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.pricing import router as pricing_router
from app.api.v1.endpoints.products import router as products_router
from fastapi import APIRouter

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(health_router)
router.include_router(kits_router)
router.include_router(orders_router)
router.include_router(pricing_router)
router.include_router(products_router)
