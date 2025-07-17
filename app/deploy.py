# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:28
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :部署定时任务
"""
import asyncio
import signal
import sys
from contextlib import suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox
from loguru import logger
from playwright.async_api import ViewportSize

import jobs
from settings import LOG_DIR, USER_DATA_DIR, EpicSettings, RECORD_DIR
from utils import init_log

init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)


@logger.catch
async def run_job_job_with_scheduler(scheduler: AsyncIOScheduler):
    """运行 Epic Games 免费游戏收集任务并显示下次运行时间"""

    headless = "virtual" if "linux" in sys.platform else False

    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1080, min_width=1920),
        record_video_dir=RECORD_DIR,
        record_video_size=ViewportSize(width=1920, height=1080),
        humanize=0.2,
        headless=headless,
    ) as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await jobs.authorize(page)

        game_page = await browser.new_page()
        await jobs.collect_games(game_page)

        with suppress(Exception):
            for p in browser.pages:
                await p.close()

        with suppress(Exception):
            await browser.close()

    # 获取下次运行时间
    job = scheduler.get_job('epic_games_job')
    if job and job.next_run_time:
        next_run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"下次运行时间: {next_run_time}")


async def main():
    """主函数 - 初始化并启动定时任务调度器"""
    logger.info("正在启动定时任务...")

    settings = EpicSettings()

    scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')

    async def scheduled_epic_games_job():
        await run_job_job_with_scheduler(scheduler)

    scheduler.add_job(
        scheduled_epic_games_job,
        trigger=CronTrigger.from_crontab(settings.CRON_SCHEDULE, timezone='Asia/Shanghai'),
        id='epic_games_job',
        name='Epic Games 免费游戏收集任务',
        replace_existing=True,
    )

    scheduler.start()

    # 获取任务的下次运行时间
    job = scheduler.get_job('epic_games_job')
    if job and job.next_run_time:
        next_run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        logger.success(f"定时任务调度器已启动，下次运行时间: {next_run_time}")
    else:
        logger.success("定时任务调度器已启动")

    # 立即运行一次任务
    logger.info("首次运行 Epic Games 免费游戏收集任务")
    await run_job_job_with_scheduler(scheduler)

    # 检查是否为单次触发模式
    if settings.IS_SINGLE_TRIGGER:
        logger.success("单次触发模式：任务执行完毕，正在关闭调度器...")
        scheduler.shutdown()
        return

    def shutdown_handler(signum, frame):
        logger.info("接收到关闭信号，正在停止调度器...")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        while True:
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号，正在停止调度器...")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"程序运行时发生错误: {e}")
        scheduler.shutdown()
        raise


if __name__ == '__main__':
    asyncio.run(main())
