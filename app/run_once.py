# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:28
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    : 单次运行任务
"""
import asyncio
import sys

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


@logger.catch
async def run_job_once():
    """运行一次 Epic Games 免费游戏收集任务"""
    logger.info("开始运行 Epic Games 免费游戏收集任务")

    headless = "virtual" if "linux" in sys.platform else False

    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1000, min_width=1440),
        humanize=0.3,
        headless=headless,
        timeout=60000,
    ) as browser:
        page = await browser.new_page()
        await jobs.authorize(page)

        game_page = await browser.new_page()
        await jobs.collect_games(game_page)

    logger.success("任务完成，程序即将退出")


async def main():
    """主函数 - 运行一次任务并退出"""
    await run_job_once()


if __name__ == '__main__':
    asyncio.run(main())