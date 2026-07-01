import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete

from backend.auth.entities import LoginAttempt, RefreshToken
from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.logger import get_logger

logger = get_logger(__name__)


async def run_cleanup() -> None:
    logger.info("cleanup initiated")
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        await db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        await db.execute(
            delete(LoginAttempt).where(
                LoginAttempt.attempted_at < now - settings.login_attempt_retain
            )
        )
        await db.commit()


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval.total_seconds())
        await run_cleanup()
