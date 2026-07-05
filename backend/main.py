import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.auth.exceptions import AuthException
from backend.config import settings
from backend.limiter import limiter
from backend.logger import configure_logging, get_logger
from backend.middleware.logging_context import LoggingContextMiddleware
from backend.routers import register_routers
from backend.tasks import cleanup_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info("app starting")

    app = FastAPI(
        title="MuminMate",
        description="Islamic knowledge chatbot rooted in Quran and authentic hadith.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(LoggingContextMiddleware)

    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc.detail)}
        ),
    )
    app.add_exception_handler(
        AuthException,
        lambda request, exc: JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        ),
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")

    register_routers(app)

    return app


app = create_app()
