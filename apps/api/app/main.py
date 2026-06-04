from app.api.router import api_router
from app.core.config import settings
from fastapi import FastAPI

app = FastAPI(title=settings.APP_NAME)

app.include_router(api_router)
