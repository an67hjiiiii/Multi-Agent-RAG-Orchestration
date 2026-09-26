from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import settings

def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name)
    application.include_router(health_router)
    application.include_router(auth_router)
    return application
app = create_app()