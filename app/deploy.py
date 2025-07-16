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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox
from loguru import logger

import jobs
from settings import LOG_DIR, USER_DATA_DIR
from utils import init_log

init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)


async def run_job_job_with_scheduler(scheduler):
    """运行 Epic Games 免费游戏收集任务并显示下次运行时间"""
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1000, min_width=1440),
        humanize=0.2,
    ) as browser:
        page = await browser.new_page()
        await jobs.collect_games(page)

    # 获取下次运行时间
    job = scheduler.get_job('epic_games_job')
    if job and job.next_run_time:
        next_run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"下次运行时间: {next_run_time}")
    else:
        logger.info("无法获取下次运行时间")


async def main():
    """主函数 - 初始化并启动定时任务调度器"""
    logger.info("正在启动定时任务...")

    # 创建异步调度器
    scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')

    # 创建包装函数，用于在任务完成后显示下次运行时间
    async def scheduled_epic_games_job():
        await run_job_job_with_scheduler(scheduler)

    # 添加定时任务：每小时运行1次
    scheduler.add_job(
        scheduled_epic_games_job,
        trigger=CronTrigger(minute=0, timezone='Asia/Shanghai'),
        id='epic_games_job',
        name='Epic Games 免费游戏收集任务',
        replace_existing=True,
    )

    # 启动调度器
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

    # 设置优雅关闭
    def shutdown_handler(signum, frame):
        logger.info("接收到关闭信号，正在停止调度器...")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # 保持程序运行
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
