# -*- coding: utf-8 -*-
# Time       : 2023/11/21 21:23
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import List

import importlib_metadata
from hcaptcha_challenger import install
from hcaptcha_challenger.agents import Malenia
from loguru import logger
from playwright.async_api import BrowserContext, async_playwright, Response, Page
from tenacity import *

from middleware.epic_search_store_query import SearchStoreQuery
from epic_games import (
    EpicPlayer,
    EpicGames,
    Game,
    CompletedOrder,
    get_promotions,
    get_order_history,
)
import urllib.parse

self_supervised = True


@dataclass
class RuYuan:
    player: EpicPlayer

    promotions: List[Game] = field(default_factory=list)
    ctx_cookies_is_available: bool = None
    headless: bool = True
    locale: str = "en-US"

    _orders = None
    _namespaces = None
    _pros = None

    task_queue: asyncio.Queue = None
    task = None

    def __post_init__(self):
        self._orders: List[CompletedOrder] = []
        self._namespaces: List[str] = []
        self._pros: List[Game] = []

        self.task_queue = asyncio.Queue(1)

    async def handler(self, response: Response):
        if response.url.startswith("https://store.epicgames.com/graphql"):
            try:
                data = await response.json()
                print(data)
                self.task_queue.put_nowait(data)
            except asyncio.QueueFull as err:
                logger.warning("ignore task", err=err)
            except Exception as err:
                logger.exception(err)

    @retry(
        retry=retry_if_exception_type(asyncio.QueueEmpty),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(30) | stop_after_attempt(60)),
        reraise=True,
    )
    async def _reset_state(self):
        self.task = self.task_queue.get_nowait()

    @classmethod
    def from_epic(cls):
        return cls(player=EpicPlayer.from_account())

    @property
    def cookies(self):
        return self.player.cookies

    def create_tasks(self):
        if not self._orders:
            self._orders = get_order_history(self.cookies)
        if not self._namespaces:
            self._namespaces = [order.namespace for order in self._orders]
        if not self._pros:
            self._pros = get_promotions()
            for pro in self._pros:
                logger.debug("Put task", title=pro.title, url=pro.url)

        self.promotions = [p for p in self._pros if p.namespace not in self._namespaces]

    async def prelude_with_context(self, context: BrowserContext) -> bool | None:
        url = "https://www.epicgames.com/account/creator-programs"
        page = context.pages[0]
        await page.goto(url, wait_until="networkidle")
        if not page.url.startswith(url):
            return

        self.ctx_cookies_is_available = True
        await context.storage_state(path=self.player.ctx_cookie_path)
        cookies = self.player.ctx_cookies.reload(self.player.ctx_cookie_path)
        self.player.cookies = cookies

        page.on("response", self.handler)
        ssq = SearchStoreQuery()
        full_url = ssq.query_all_promotions()
        await page.goto(full_url)
        await self._reset_state()

        if not self.promotions:
            logger.success(
                "Pass claim task",
                reason="All free games are in my library",
                stage="context-prelude",
            )
            return True

    async def claim_epic_games(self, context: BrowserContext):
        page = context.pages[0]
        epic = EpicGames.from_player(self.player, page=page, self_supervised=self_supervised)

        if not self.ctx_cookies_is_available:
            logger.info("Try to flush cookie", task="claim_epic_games")
            if await epic.authorize(page):
                cookies = await epic.flush_token(context)
                self.player.cookies = cookies
            else:
                logger.error("Exit task", reason="Failed to flush token")
                return

        if not self.promotions:
            self.create_tasks()
        if not self.promotions:
            logger.success(
                "Pass claim task", reason="All free games are in my library", stage="claim-games"
            )
            return

        single_promotions = []
        bundle_promotions = []
        for p in self.promotions:
            if "bundles" in p.url:
                bundle_promotions.append(p)
            else:
                single_promotions.append(p)

        if single_promotions:
            await epic.claim_weekly_games(page, single_promotions)
        if bundle_promotions:
            await epic.claim_bundle_games(page, bundle_promotions)

    @logger.catch
    async def stash(self):
        if "linux" in sys.platform and "DISPLAY" not in os.environ:
            self.headless = True

        logger.info(
            "get",
            image="20231121",
            version=importlib_metadata.version("hcaptcha-challenger"),
            role="EpicPlayer",
            headless=self.headless,
        )

        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                user_data_dir=self.player.browser_context_dir,
                record_video_dir=self.player.record_dir,
                record_har_path=self.player.record_har_path,
                headless=self.headless,
                locale=self.locale,
                args=["--hide-crash-restore-bubble"],
            )
            await Malenia.apply_stealth(context)

            page = context.pages[0]
            ssq = SearchStoreQuery()
            full_url = ssq.query_all_promotions()
            print(full_url)

            await page.goto(full_url)

            await page.pause()

            await context.close()


async def run():
    agent = RuYuan.from_epic()
    agent.headless = False
    await agent.stash()


if __name__ == "__main__":
    asyncio.run(run())
