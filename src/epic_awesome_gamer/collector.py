# -*- coding: utf-8 -*-
# Time       : 2023/8/16 5:14
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import json
from typing import List

from loguru import logger
from playwright.async_api import Page

from epic_awesome_gamer import get_promotions, EpicGames, EpicSettings
from epic_awesome_gamer.epic_games import URL_CLAIM
from epic_awesome_gamer.types import PromotionGame, OrderItem, Order
from hcaptcha_challenger.agent import AgentConfig


class EpicAgent:

    def __init__(
        self,
        page: Page,
        epic_settings: EpicSettings | None = None,
        solver_config: AgentConfig | None = None,
    ):
        self.page = page

        self.epic_settings = epic_settings or EpicSettings()
        solver_config = solver_config or AgentConfig(DISABLE_BEZIER_TRAJECTORY=True)

        self.epic_games = EpicGames(
            self.page, epic_settings=self.epic_settings, solver_config=solver_config
        )

        self._promotions: List[PromotionGame] = []
        self._ctx_cookies_is_available: bool = False
        self._orders: List[OrderItem] = []
        self._namespaces: List[str] = []

        self._cookies = None

    async def _sync_order_history(self):
        """获取最近的订单纪录"""
        if self._orders:
            return

        completed_orders: List[OrderItem] = []

        try:
            await self.page.goto("https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory")
            text_content = await self.page.text_content("//pre")
            data = json.loads(text_content)
            for _order in data["orders"]:
                order = Order(**_order)
                if order.orderType != "PURCHASE":
                    continue
                for item in order.items:
                    if not item.namespace or len(item.namespace) != 32:
                        continue
                    completed_orders.append(item)
        except Exception as err:
            logger.warning(err)

        self._orders = completed_orders

    async def _check_orders(self):
        # 获取玩家历史交易订单
        # 运行该操作之前必须确保账号信息有效
        await self._sync_order_history()

        self._namespaces = self._namespaces or [order.namespace for order in self._orders]

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
            return False

        # == 令牌有效 == #

        # 浏览器的身份信息仍然有效
        self._ctx_cookies_is_available = True

        # 加载正交的优惠商品数据
        await self._check_orders()

        # 促销列表为空，说明免费游戏都已收集，任务结束
        if not self._promotions:
            logger.success("✅ All week-free games are already in the library")
            return True

        # 账号信息有效，但还存在没有领完的游戏
        return False

    async def collect_epic_games(self):
        if await self._should_ignore_task():
            return

        # 刷新浏览器身份信息
        if not self._ctx_cookies_is_available:
            logger.info("Try to flush cookie")
            if not await self.epic_games.authorize(self.page):
                logger.error("❌ Failed to flush token")
                return

        # 加载正交的优惠商品数据
        if not self._promotions:
            await self._check_orders()

        if not self._promotions:
            logger.success("✅ All week-free games are already in the library")
            return

        game_promotions = []
        bundle_promotions = []
        for p in self._promotions:
            logger.debug(f"✅ Discover promotion《{p.title}》 url={p.url}")
            if "/bundles/" in p.url:
                bundle_promotions.append(p)
            else:
                game_promotions.append(p)

        # 收集优惠游戏
        if game_promotions:
            try:
                await self.epic_games.collect_weekly_games(game_promotions)
            except Exception as e:
                logger.exception(e)

        # 收集游戏捆绑内容
        if bundle_promotions:
            logger.debug("Skip the game bundled content")

        logger.debug("✅ Workflow ends")
