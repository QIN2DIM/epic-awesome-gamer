# -*- coding: utf-8 -*-
"""
Epic Games Free Game Collection Deployment Module

This module orchestrates the automated collection of free games from Epic Games Store
using browser automation and scheduling capabilities.

@Time    : 2025/7/16 21:28
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
"""

import asyncio
import json
import signal
import sys
from contextlib import suppress
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox
from loguru import logger
from playwright.async_api import ViewportSize
from pytz import timezone

from services.epic_authorization_service import EpicAuthorization
from services.epic_games_service import EpicAgent
from settings import LOG_DIR, RECORD_DIR
from settings import settings
from utils import init_log

# Initialize logging configuration for runtime, error, and serialization logs
init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)

# Default timezone for scheduling operations
TIMEZONE = timezone("Asia/Shanghai")


@logger.catch
async def execute_browser_tasks(headless: bool = True):
    """
    Execute Epic Games free game collection tasks using browser automation.

    This function handles the complete workflow of authenticating with Epic Games
    and collecting available free games through browser automation.

    Args:
        headless: Whether to run browser in headless mode
    """
    logger.debug("Starting Epic Games collection task")

    # Configure browser with anti-detection features and video recording
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=settings.user_data_dir,
        screen=Screen(max_width=1920, max_height=1080, min_height=1080, min_width=1920),
        record_video_dir=RECORD_DIR,
        record_video_size=ViewportSize(width=1920, height=1080),
        humanize=0.2,
        headless=headless,
    ) as browser:
        # Initialize or reuse existing browser page
        page = browser.pages[0] if browser.pages else await browser.new_page()
        logger.debug("Browser initialized successfully")

        # Handle Epic Games authentication
        logger.debug("Initiating Epic Games authentication")
        agent = EpicAuthorization(page)
        await agent.invoke()
        logger.debug("Authentication completed")

        # Execute a free games collection on new page
        logger.debug("Starting free games collection process")
        game_page = await browser.new_page()
        agent = EpicAgent(game_page)
        await agent.collect_epic_games()
        logger.debug("Free games collection completed")

        # Cleanup browser resources
        logger.debug("Cleaning up browser resources")
        with suppress(Exception):
            for p in browser.pages:
                await p.close()

        with suppress(Exception):
            await browser.close()

        logger.debug("Browser tasks execution finished successfully")


async def deploy():
    """
    Main deployment function that executes Epic Games collection tasks.

    This function runs the collection process immediately and optionally
    sets up a scheduled task for automatic recurring execution.
    """
    headless = True

    # Log current configuration for debugging
    sj = settings.model_dump(mode="json")
    sj["headless"] = headless
    logger.debug(
        f"Starting deployment with configuration: {json.dumps(sj, indent=2, ensure_ascii=False)}"
    )

    # Execute an immediate collection task
    await execute_browser_tasks(headless=headless)

    # Skip scheduler setup if disabled in configuration
    if not settings.ENABLE_APSCHEDULER:
        logger.debug("Scheduler is disabled, deployment completed")
        return

    # Initialize and configure async scheduler
    scheduler = AsyncIOScheduler()

    # Strategy 1: Thursday 23:30 to Friday 03:30, every hour (Beijing Time)
    scheduler.add_job(
        execute_browser_tasks,
        trigger=CronTrigger(
            day_of_week="thu", hour="23,0,1,2,3", minute="30", timezone="Asia/Shanghai"
        ),
        id="weekly_epic_games_task",
        name="weekly_epic_games_task",
        args=[headless],
        replace_existing=False,
        max_instances=1,
    )

    # Strategy 2: Daily at 12:00 PM (Beijing Time)
    scheduler.add_job(
        execute_browser_tasks,
        trigger=CronTrigger(hour="12", minute="0", timezone="Asia/Shanghai"),
        id="daily_epic_games_task",
        name="daily_epic_games_task",
        args=[headless],
        replace_existing=False,
        max_instances=1,
    )

    # Set up graceful shutdown signal handlers
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.debug(f"Received signal {signal.Signals(signum).name}, initiating graceful shutdown")
        shutdown_event.set()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start scheduler and log status information
    scheduler.start()
    logger.debug("Epic Games scheduler started successfully")
    logger.debug(f"Current time: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Log next execution times for all scheduled jobs
    for j in scheduler.get_jobs():
        if next_run := j.next_run_time:
            logger.debug(
                f"Next execution scheduled: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} (job_id: {j.id})"
            )

    # Keep scheduler running until shutdown signal received
    logger.debug("Scheduler is running, send SIGINT or SIGTERM to stop gracefully")
    try:
        await shutdown_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=True)
        logger.success("Scheduler stopped gracefully")


if __name__ == '__main__':
    asyncio.run(deploy())
