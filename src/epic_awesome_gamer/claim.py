# -*- coding: utf-8 -*-
# Time       : 2023/8/16 5:14
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import asyncio
from pathlib import Path
from typing import List

from loguru import logger
from playwright.async_api import BrowserContext, async_playwright, ViewportSize, Page

from epic_awesome_gamer import get_order_history, get_promotions, EpicGames, EpicSettings
from epic_awesome_gamer.types import PromotionGame, CompletedOrder


class EpicAgent:

    def __init__(self, page: Page):
        self.page = page

        self._promotions: List[PromotionGame] = []
        self._ctx_cookies_is_available: bool = False
        self._orders: List[CompletedOrder] = []
        self._namespaces: List[str] = []
        self._pros: List[PromotionGame] = []

        self._cookies = None

    async def _create_tasks(self):
        if not self._orders:
            storage_state = await self.page.context.storage_state()
            _cookies = {ck["name"]: ck["value"] for ck in storage_state["cookies"]}
            self._orders = get_order_history(_cookies)
        if not self._namespaces:
            self._namespaces = [order.namespace for order in self._orders]
        if not self._pros:
            self._pros = get_promotions()
            for pro in self._pros:
                logger.debug("Put task", title=pro.title, url=pro.url)

        self._promotions = [p for p in self._pros if p.namespace not in self._namespaces]

    async def _should_ignore_task(self) -> bool:
        url = "https://www.epicgames.com/account/code-redemption"

        await self.page.goto(url, wait_until="networkidle")

        # 被重定向，浏览器没有缓存登录信息
        if not self.page.url.startswith(url):
            return False

        # 浏览器的身份信息仍然有效
        self._ctx_cookies_is_available = True

        await self._create_tasks()

        # 促销列表为空，说明免费游戏都已收集
        if not self._promotions:
            logger.success("All free games are in my library")
            return True

        return False

    async def collect_epic_games(self):
        if not await self._should_ignore_task():
            return

        epic_settings = EpicSettings()
        epic = EpicGames(self.page, settings=epic_settings)

        authorize_page = await self.page.context.new_page()

        _cookies = None
        if not self._ctx_cookies_is_available:
            logger.info("Try to flush cookie")
            if await epic.authorize(authorize_page):
                _cookies = await epic.flush_token(self.page.context, path="ctx_cookies.json")
            else:
                logger.error("❌ Failed to flush token")
                return

        if not self._promotions:
            await self._create_tasks()

        if not self._promotions:
            logger.success("✅ All free games are in my library")
            return

        single_promotions = []
        bundle_promotions = []
        for p in self._promotions:
            if "bundles" in p.url:
                bundle_promotions.append(p)
            else:
                single_promotions.append(p)

        worker_page = await self.page.context.new_page()

        if single_promotions:
            await epic.collect_weekly_games(worker_page, single_promotions)
        if bundle_promotions:
            await epic.collect_bundle_games(worker_page, bundle_promotions)


async def startup_epic_awesome_gamer(context: BrowserContext):
    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    agent = EpicAgent(page)

    await agent.collect_epic_games()


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="tmp/.cache/user_data",
            record_video_dir=Path("tmp/.cache/record"),
            record_video_size=ViewportSize(width=1920, height=1080),
            headless=False,
            locale="en-US",
        )

        await startup_epic_awesome_gamer(context)


if __name__ == "__main__":
    asyncio.run(main())
