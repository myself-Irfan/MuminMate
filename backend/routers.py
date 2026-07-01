from fastapi import FastAPI

from backend.auth.router import router as auth_router
from backend.views.auth_views import router as auth_view_router
from backend.views.chat_views import router as chat_view_router


def register_routers(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(auth_view_router)
    app.include_router(chat_view_router)
