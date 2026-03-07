from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings


def get_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    engine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
