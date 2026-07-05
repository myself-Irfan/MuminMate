import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ensure all entity tables are registered with Base.metadata before create_all
import backend.auth.entities  # noqa: F401
import backend.threads.entities  # noqa: F401
from backend.config import settings
from backend.database import Base, get_db
from backend.main import app

_engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db():
    from backend.limiter import limiter

    limiter.enabled = False  # rate limiting is tested in integration, not unit tests

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with _TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    payload = {"email": "user@example.com", "username": "testuser", "password": "password123"}
    await client.post("/api/auth/register", json=payload)
    return payload


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, registered_user: dict) -> AsyncClient:
    resp = await client.post("/api/auth/login", json=registered_user)
    access_token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    return client
