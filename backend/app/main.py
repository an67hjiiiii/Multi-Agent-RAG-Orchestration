from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name)

    danh_sach_nguon_goc = [
        nguon_goc.strip()
        for nguon_goc in settings.cors_origins.split(",")
        if nguon_goc.strip()
    ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=danh_sach_nguon_goc,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(knowledge_router)
    return application


app = create_app()