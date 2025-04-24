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
from epic_awesome_gamer.epic_games import URL_CLAIM
from epic_awesome_gamer.types import PromotionGame, CompletedOrder


class EpicAgent:

    def __init__(self, page: Page):
        self.page = page

        self._promotions: List[PromotionGame] = []
        self._ctx_cookies_is_available: bool = False
        self._orders: List[CompletedOrder] = []
        self._namespaces: List[str] = []

        self._cookies = None

    async def _check_orders(self):
        # 获取玩家历史交易订单
        # 运行该操作之前必须确保账号信息有效
        if not self._orders:
            storage_state = await self.page.context.storage_state()
            _cookies = {ck["name"]: ck["value"] for ck in storage_state["cookies"]}
            self._orders = get_order_history(_cookies)

        if not self._namespaces:
            self._namespaces = [order.namespace for order in self._orders]

        # 获取本周促销数据
        # 正交数据，得到还未收集的优惠商品
        self._promotions = [p for p in get_promotions() if p.namespace not in self._namespaces]

    async def _should_ignore_task(self) -> bool:
        self._ctx_cookies_is_available = False

        # 判断浏览器是否已缓存账号令牌信息
        await self.page.goto(URL_CLAIM, wait_until="domcontentloaded")

        # == 令牌过期 == #
        status = await self.page.locator("//egs-navigation").get_attribute("isloggedin")
        if status == "false":
            logger.debug("The token has expired and needs to be logged in again")
            return False

        # == 令牌有效 == #

        # 浏览器的身份信息仍然有效
        self._ctx_cookies_is_available = True

        # 加载正交的优惠商品数据
        await self._check_orders()

        # 促销列表为空，说明免费游戏都已收集，任务结束
        if not self._promotions:
            logger.success("✅ All free games are in my library")
            return True

        # 账号信息有效，但还存在没有领完的游戏
        return False

    async def collect_epic_games(self):
        if await self._should_ignore_task():
            return

        epic_settings = EpicSettings()
        epic = EpicGames(self.page, settings=epic_settings)

        _cookies = None

        # 刷新浏览器身份信息
        if not self._ctx_cookies_is_available:
            logger.info("Try to flush cookie")
            if await epic.authorize(self.page):
                _cookies = await epic.flush_token(self.page.context, path="ctx_cookies.json")
            else:
                logger.error("❌ Failed to flush token")
                return

        # 加载正交的优惠商品数据
        if not self._promotions:
            await self._check_orders()

        if not self._promotions:
            logger.success("✅ All free games are in my library")
            return

        single_promotions = []
        bundle_promotions = []
        for p in self._promotions:
            logger.debug(f"Add Productions - title={p.title} url={p.url}")
            if "bundles" in p.url:
                bundle_promotions.append(p)
            else:
                single_promotions.append(p)

        worker_page = await self.page.context.new_page()

        # 收集优惠游戏
        if single_promotions:
            try:
                await epic.collect_weekly_games(worker_page, single_promotions)
            except Exception as e:
                logger.exception(e)

        # 收集游戏捆绑内容
        if bundle_promotions:
            try:
                await epic.collect_bundle_games(worker_page, bundle_promotions)
            except Exception as e:
                logger.exception(e)
