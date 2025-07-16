# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:28
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :部署定时任务
"""
import asyncio

from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox

import jobs
from settings import LOG_DIR, USER_DATA_DIR
from utils import init_log

init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)


async def invoke():
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1000, min_width=1440),
        humanize=0.2,
    ) as browser:
        page = browser.pages[-1] if browser.pages else await browser.new_page()
        await jobs.collect_games(page)


async def main():
    await invoke()


if __name__ == '__main__':
    asyncio.run(main())
