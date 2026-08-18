import asyncio

from src.db.session import init_db
from src.middleware.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("running_manual_db_seed")
    await init_db()
    logger.info("db_seed_completed_successfully")


if __name__ == "__main__":
    asyncio.run(main())
