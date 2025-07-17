# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:28
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :部署定时任务
"""
import asyncio
import sys
from contextlib import suppress

from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox
from loguru import logger
from playwright.async_api import ViewportSize

import jobs
from settings import LOG_DIR, USER_DATA_DIR, RECORD_DIR
from utils import init_log

init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)


@logger.catch
async def main():
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


if __name__ == '__main__':
    asyncio.run(main())
