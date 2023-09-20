# -*- coding: utf-8 -*-
# Time       : 2023/8/16 5:14
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import List

import hcaptcha_challenger as solver
from loguru import logger
from playwright.async_api import BrowserContext, async_playwright

from services.agents.epic_games import EpicPlayer, EpicGames, Game
from services.agents.epic_games import get_promotions, get_order_history


@dataclass
class ISurrender:
    player: EpicPlayer

    promotions: List[Game] = field(default_factory=list)
    ctx_cookies_is_available: bool = None
    headless: bool = True
    locale: str = "en-US"

    def __post_init__(self):
        if "linux" in sys.platform and "DISPLAY" not in os.environ:
            self.headless = True

    @classmethod
    def from_epic(cls):
        logger.info("run", stage="Initialization EpicPlayer")
        return cls(player=EpicPlayer.from_account())

    @property
    def cookies(self):
        return self.player.cookies

    def create_tasks(self):
        orders = get_order_history(self.cookies)
        namespaces = [order.namespace for order in orders]
        pros = get_promotions()
        for pro in pros:
            logger.debug("Put task", title=pro.title, url=pro.url)
        self.promotions = [p for p in pros if p.namespace not in namespaces]

    def prelude(self):
        if not self.player.ctx_cookies.is_available():
            return
        self.ctx_cookies_is_available = True
        self.create_tasks()
        if not self.promotions:
            logger.success(
                "Pass claim task", reason="All free games are in my library", stage="prelude"
            )
            sys.exit()

    async def flush_cookies(self, context):
        await context.storage_state(path=self.player.ctx_cookie_path)
        cookies = self.player.ctx_cookies.reload(self.player.ctx_cookie_path)
        self.player.cookies = cookies

    async def prelude_with_context(self, context: BrowserContext) -> bool | None:
        url = "https://www.epicgames.com/account/personal"
        res = await context.request.get(url, max_redirects=0)
        if res.status != 200:
            return

        self.ctx_cookies_is_available = True
        await self.flush_cookies(context)
        self.create_tasks()
        if not self.promotions:
            logger.success(
                "Pass claim task",
                reason="All free games are in my library",
                stage="context-prelude",
            )
            return True

    async def claim_epic_games(self, context: BrowserContext):
        page = context.pages[0]
        epic = EpicGames.from_player(self.player, page=page)

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

        await epic.claim_weekly_games(page, self.promotions)

    @logger.catch
    async def stash(self):
        self.prelude()

        async with async_playwright() as p:
            context = await p.firefox.launch_persistent_context(
                user_data_dir=self.player.browser_context_dir,
                record_video_dir=self.player.record_dir,
                record_har_path=self.player.record_har_path,
                headless=self.headless,
                locale=self.locale,
                args=["--hide-crash-restore-bubble"],
            )
            if not await self.prelude_with_context(context):
                solver.install(upgrade=True)
                await self.claim_epic_games(context)


async def run():
    agent = ISurrender.from_epic()
    await agent.stash()


if __name__ == "__main__":
    asyncio.run(run())
