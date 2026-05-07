from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import settings
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Rome")


def init_scheduler():
    from orchestrator import run_pipeline

    scheduler.add_job(
        run_pipeline,
        "cron",
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        id="daily_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler avviato: pipeline giornaliera alle {settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} (Europe/Rome)")
