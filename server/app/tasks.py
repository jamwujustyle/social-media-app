import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from celery import shared_task
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import SessionLocal
from app.user.models import User
from app.logging_config import logger


async def async_cleanup_unverified_users(db: Optional[AsyncSession] = None) -> int:
    """
    Async logic to delete all users who have not verified their account
    and whose verification code has expired (more than 24 hours old).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    logger.info(
        f"Scanning for unverified users with expired verification codes before {cutoff.isoformat()}"
    )

    if db is not None:
        return await _execute_cleanup(db, cutoff)

    async with SessionLocal() as session:
        return await _execute_cleanup(session, cutoff)


async def _execute_cleanup(db: AsyncSession, cutoff: datetime) -> int:
    stmt = select(User).where(
        User.is_verified == False,
        or_(
            User.created_at <= cutoff,
            User.verification_code_expires_at <= cutoff,
        ),
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    count = len(users)

    if count > 0:
        emails = [u.email for u in users]
        logger.info(
            f"Found {count} unverified users with expired codes for cleanup: {emails}"
        )

        # Execute deletion
        delete_stmt = (
            delete(User)
            .where(
                User.is_verified == False,
                or_(
                    User.created_at <= cutoff,
                    User.verification_code_expires_at <= cutoff,
                ),
            )
            .execution_options(synchronize_session=False)
        )
        await db.execute(delete_stmt)
        await db.commit()
        logger.info(f"Successfully deleted {count} unverified users.")
    else:
        logger.info("No unverified users met the cleanup criteria.")

    return count


@shared_task(name="app.tasks.cleanup_unverified_users")
def cleanup_unverified_users() -> int:
    """
    Celery task that acts as a wrapper around the async database cleanup logic.
    """
    logger.info("Starting cleanup of unverified users...")
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(async_cleanup_unverified_users())
    finally:
        loop.close()
