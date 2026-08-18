from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.db.models import User
from src.middleware.logging import get_logger
from src.utils.security import hash_password

logger = get_logger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SEED_USERS = [
    {
        "id": "usr_test_1",
        "name": "User 1",
        "email": "user1@docqa.ai",
        "password": "password123",
        "role": "Researcher",
    },
    {
        "id": "usr_test_2",
        "name": "User 2",
        "email": "user2@docqa.ai",
        "password": "password123",
        "role": "Analyst",
    },
]


async def init_db() -> None:
    try:
        async with async_session_maker() as session:
            existing = (await session.execute(select(User.id).limit(1))).first()
            if existing:
                logger.info("database_ready")
                return

            for user_data in SEED_USERS:
                session.add(
                    User(
                        id=user_data["id"],
                        name=user_data["name"],
                        email=user_data["email"],
                        password_hash=hash_password(user_data["password"]),
                        role=user_data["role"],
                    )
                )
            await session.commit()
            logger.info("database_seeded", user_count=len(SEED_USERS))
    except Exception as exc:
        logger.error("database_seed_failed", error=str(exc))
