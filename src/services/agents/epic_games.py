# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import List, Dict

import httpx
from hcaptcha_challenger.agents.playwright.control import AgentT
from loguru import logger
from playwright.sync_api import BrowserContext, expect, TimeoutError
from playwright.sync_api import Page

from services.models import EpicPlayer
from utils import from_dict_to_model

# fmt:off
URL_CLAIM = "https://store.epicgames.com/en-US/free-games"
URL_LOGIN = f"https://www.epicgames.com/id/login?lang=en-US&noHostRedirect=true&redirectUrl={URL_CLAIM}"
URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
URL_PRODUCT_PAGE = "https://store.epicgames.com/en-US/p/"
URL_ORDER_HISTORY = "https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory"
URL_CART = "https://store.epicgames.com/en-US/cart"
URL_CART_SUCCESS = "https://store.epicgames.com/en-US/cart/success"
# -----
URL_STORE_EXPLORER = "https://store.epicgames.com/en-US/browse?sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&count=40"
URL_STORE_EXPLORER_GRAPHQL = (
    "https://store.epicgames.com/graphql?operationName=searchStoreQuery"
    '&variables={"category":"games/edition/base","comingSoon":false,"count":80,"freeGame":true,"keywords":"","sortBy":"releaseDate","sortDir":"DESC","start":0,"tag":"","withPrice":true}'
    '&extensions={"persistedQuery":{"version":1,"sha256Hash":"13a2b6787f1a20d05c75c54c78b1b8ac7c8bf4efc394edf7a5998fdf35d1adb0"}}'
)


# fmt:on


@dataclass
class CompletedOrder:
    offerId: str
    namespace: str


@dataclass
class Game:
    url: str
    namespace: str
    title: str
    thumbnail: str
    in_library = None


@dataclass
class EpicGames:
    player: EpicPlayer
    """
    Agent control
    """

    _solver: AgentT = None
    """
    Module for anti-captcha
    """

    _promotions: List[Game] = field(default_factory=list)
    """
    Free promotional items for the week, 
    considered metadata for task sequence of the agent
    """

    @classmethod
    def from_player(
        cls, player: EpicPlayer, *, page: Page, tmp_dir: Path | None = None, **solver_opt
    ):
        """尽可能早地实例化，用于部署 captcha 事件监听器"""
        return cls(
            player=player, _solver=AgentT.from_page(page=page, tmp_dir=tmp_dir, **solver_opt)
        )

    @property
    def promotions(self) -> List[Game]:
        self._promotions = self._promotions or get_promotions()
        return self._promotions

    def _login(self, page: Page) -> str | None:
        page.goto(URL_CLAIM, wait_until="domcontentloaded")
        while page.locator('a[role="button"]:has-text("Sign In")').count() > 0:
            page.goto(URL_LOGIN, wait_until="domcontentloaded")
            logger.info("login", url=page.url)
            page.click("#login-with-epic")
            logger.info("login-with-epic", url=page.url)
            page.fill("#email", self.player.email)
            page.type("#password", self.player.password)
            page.click("#sign-in")

            fall_in_challenge = False

            for _ in range(15):
                if not fall_in_challenge:
                    with suppress(TimeoutError):
                        page.wait_for_url(URL_CLAIM, timeout=10000)
                        break
                    if not self._solver.qr:
                        return
                fall_in_challenge = True
                result = self._solver(window="login", recur_url=URL_CLAIM)
                if result in [
                    self._solver.status.CHALLENGE_BACKCALL,
                    self._solver.status.CHALLENGE_RETRY,
                ]:
                    page.click("//a[@class='talon_close_button']")
                    page.wait_for_timeout(1000)
                    page.click("#sign-in", delay=200)
                    continue
                if result == self._solver.status.CHALLENGE_SUCCESS:
                    page.wait_for_url(URL_CLAIM)
                    break

        return self._solver.status.AUTH_SUCCESS

    def authorize(self, page: Page):
        for _ in range(3):
            result = self._login(page)
            if result not in [self._solver.status.CHALLENGE_SUCCESS]:
                continue
            return True
        logger.critical("Failed to flush token", agent=self.__class__.__name__)

    def flush_token(self, context: BrowserContext):
        page = context.pages[0]
        page.goto("https://www.epicgames.com/account/personal", wait_until="networkidle")
        page.goto(
            "https://store.epicgames.com/zh-CN/p/orwell-keeping-an-eye-on-you",
            wait_until="networkidle",
        )
        context.storage_state(path=self.player.ctx_cookie_path)
        self.player.ctx_cookies.reload(self.player.ctx_cookie_path)
        logger.success("flush_token", path=self.player.ctx_cookie_path)

    def claim_weekly_games(self, page: Page, promotions: List[Game]):
        """

        :param page:
        :param promotions: 未在库的 promotions
        :return:
        """
        # --> Add promotions to Cart
        for promotion in promotions:
            logger.info("claim_weekly_games", action="go to store", url=promotion.url)
            page.goto(promotion.url, wait_until="load")

            # <-- Handle pre-page
            with suppress(TimeoutError):
                page.click("//button//span[text()='Continue']", timeout=3000)

            # --> Make sure promotion is not in the library before executing
            cta_btn = page.locator("//aside//button[@data-testid='add-to-cart-cta-button']")
            text = cta_btn.text_content()
            if text == "View In Cart":
                continue
            if text == "Add To Cart":
                cta_btn.click()
                expect(cta_btn).to_have_text("View In Cart")

        # --> Goto cart page
        page.goto(URL_CART, wait_until="domcontentloaded")
        page.click("//button//span[text()='Check Out']")

        # <-- Handle Any LICENSE
        with suppress(TimeoutError):
            page.click("//label[@for='agree']", timeout=2000)
            accept = page.locator("//button//span[text()='Accept']")
            if accept.is_enabled():
                accept.click()

        # --> Move to webPurchaseContainer iframe
        logger.info("claim_weekly_games", action="move to webPurchaseContainer iframe")
        wpc = page.frame_locator("//iframe[@class='']")
        payment_btn = wpc.locator("//div[@class='payment-order-confirm']")
        with suppress(Exception):
            expect(payment_btn).to_be_attached()
        page.wait_for_timeout(2000)
        payment_btn.click()
        logger.info("claim_weekly_games", action="click payment button")

        # <-- Insert challenge

        fall_in_challenge = False

        for _ in range(8):
            if not fall_in_challenge:
                with suppress(TimeoutError):
                    page.wait_for_url(URL_CART_SUCCESS, timeout=10000)
                    break
            fall_in_challenge = True
            result = self._solver(window="free", recur_url=URL_CART_SUCCESS)
            logger.debug("claim_weekly_games", action="challenge", result=result)
            if result in [
                self._solver.status.CHALLENGE_BACKCALL,
                self._solver.status.CHALLENGE_RETRY,
            ]:
                wpc.locator("//a[@class='talon_close_button']").click()
                page.wait_for_timeout(1000)
                payment_btn.click(delay=200)
                continue
            if result == self._solver.status.CHALLENGE_SUCCESS:
                page.wait_for_url(URL_CART_SUCCESS)
                break

        # --> Wait for success
        page.wait_for_url(URL_CART_SUCCESS)
        logger.success("claim_weekly_games", action="success", url=page.url)


def get_promotions() -> List[Game]:
    """
    获取周免游戏数据

    <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
    <本周免费> promotion["promotions"]["promotionalOffers"]
    :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
    """
    _promotions: List[Game] = []

    params = {"local": "zh-CN"}
    resp = httpx.get(URL_PROMOTIONS, params=params)
    try:
        data = resp.json()
    except JSONDecodeError:
        pass
    else:
        elements = data["data"]["Catalog"]["searchStore"]["elements"]
        promotions = [e for e in elements if e.get("promotions")]
        # 获取商城促销数据&&获取<本周免费>的游戏对象
        for promotion in promotions:
            if offer := promotion["promotions"]["promotionalOffers"]:
                # 去除打折了但只打一点点的商品
                with suppress(KeyError, IndexError):
                    offer = offer[0]["promotionalOffers"][0]
                    if offer["discountSetting"]["discountPercentage"] != 0:
                        continue
                try:
                    query = promotion["catalogNs"]["mappings"][0]["pageSlug"]
                    promotion["url"] = f"{URL_PRODUCT_PAGE}{query}"
                except IndexError:
                    promotion["url"] = f"{URL_PRODUCT_PAGE}{promotion['productSlug']}"

                promotion["thumbnail"] = promotion["keyImages"][-1]["url"]

                _promotions.append(from_dict_to_model(Game, promotion))

    return _promotions


def get_order_history(
    cookies: Dict[str, str], page: str | None = None, last_create_at: str | None = None
) -> List[CompletedOrder]:
    """获取最近的订单纪录"""

    def request_history() -> str | None:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203"
        }
        params = {"locale": "zh-CN", "page": page or "0", "latCreateAt": last_create_at or ""}
        resp = httpx.get(URL_ORDER_HISTORY, headers=headers, cookies=cookies, params=params)
        if not resp.is_success:
            raise httpx.RequestError("Failed to get order history, cookie may have expired")
        return resp.text

    completed_orders: List[CompletedOrder] = []

    try:
        data = json.loads(request_history())
        for order in data["orders"]:
            if order["orderType"] != "PURCHASE":
                continue
            for item in order["items"]:
                if len(item["namespace"]) != 32:
                    continue
                completed_orders.append(from_dict_to_model(CompletedOrder, item))
    except (httpx.RequestError, JSONDecodeError, KeyError) as err:
        logger.warning(err)

    return completed_orders
