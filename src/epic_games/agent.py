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
from typing import List, Dict, Literal

import httpx
from loguru import logger
from playwright.async_api import BrowserContext, expect, TimeoutError, Page, FrameLocator, Locator
from tenacity import *

from epic_games.player import EpicPlayer
from utils import from_dict_to_model, AgentG

# fmt:off
URL_CLAIM = "https://store.epicgames.com/en-US/free-games"
URL_LOGIN = f"https://www.epicgames.com/id/login?lang=en-US&noHostRedirect=true&redirectUrl={URL_CLAIM}"
URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
URL_PRODUCT_PAGE = "https://store.epicgames.com/en-US/p/"
URL_PRODUCT_BUNDLES = "https://store.epicgames.com/en-US/bundles/"
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
    id: str
    in_library = None


class CommonHandler:
    @staticmethod
    async def any_license(page: Page):
        with suppress(TimeoutError):
            await page.click("//label[@for='agree']", timeout=2000)
            accept = page.locator("//button//span[text()='Accept']")
            if await accept.is_enabled():
                await accept.click()

    @staticmethod
    async def move_to_purchase_container(page: Page):
        wpc = page.frame_locator("//iframe[@class='']")
        payment_btn = wpc.locator("//div[@class='payment-order-confirm']")
        with suppress(Exception):
            await expect(payment_btn).to_be_attached()
        await page.wait_for_timeout(2000)
        await payment_btn.click(timeout=6000)

        return wpc, payment_btn

    @staticmethod
    async def uk_confirm_order(wpc: FrameLocator):
        # <-- Handle UK confirm-order
        with suppress(TimeoutError):
            accept = wpc.locator(
                "//button[contains(@class, 'payment-confirm__btn payment-btn--primary')]"
            )
            if await accept.is_enabled(timeout=5000):
                await accept.click()
                return True

    @staticmethod
    @retry(
        retry=retry_if_exception_type(TimeoutError),
        wait=wait_fixed(0.5),
        stop=stop_after_attempt(15),
        reraise=True,
    )
    async def insert_challenge(
        solver: AgentG,
        page: Page,
        wpc: FrameLocator,
        payment_btn: Locator,
        recur_url: str,
        is_uk: bool,
    ):
        response = await solver.execute(window="free")
        logger.debug("task done", sattus=f"{solver.status.CHALLENGE_SUCCESS}")

        match response:
            case solver.status.CHALLENGE_BACKCALL | solver.status.CHALLENGE_RETRY:
                await wpc.locator("//a[@class='talon_close_button']").click()
                await page.wait_for_timeout(1000)
                if is_uk:
                    await CommonHandler.uk_confirm_order(wpc)
                await payment_btn.click(delay=200)
            case solver.status.CHALLENGE_SUCCESS:
                await page.wait_for_url(recur_url)
                return

    @staticmethod
    async def empty_cart(page: Page, wait_rerender: int = 30) -> bool | None:
        """
        URL_CART = "https://store.epicgames.com/en-US/cart"
        URL_WISHLIST = "https://store.epicgames.com/en-US/wishlist"
        //span[text()='Your Cart is empty.']

        Args:
            wait_rerender:
            page:

        Returns:

        """
        has_paid_free = False

        try:
            # Check all items in the shopping cart
            cards = await page.query_selector_all("//div[@data-testid='offer-card-layout-wrapper']")

            # Move paid games to wishlist games
            for card in cards:
                is_free = await card.query_selector("//span[text()='Free']")
                if not is_free:
                    has_paid_free = True
                    wishlist_btn = await card.query_selector(
                        "//button//span[text()='Move to wishlist']"
                    )
                    await wishlist_btn.click()

            # Wait up to 60 seconds for the page to re-render.
            # Usually it takes 1~3s for the web page to be re-rendered
            # - Set threshold for overflow in case of poor Epic network
            # - It can also prevent extreme situations, such as: the user’s shopping cart has nearly a hundred products
            if has_paid_free and wait_rerender:
                wait_rerender -= 1
                await page.wait_for_timeout(2000)
                return await CommonHandler.empty_cart(page, wait_rerender)
            return True
        except TimeoutError as err:
            logger.warning("Failed to empty shopping cart", err=err)
            return False


@dataclass
class EpicGames:
    player: EpicPlayer
    """
    Agent control
    """

    _solver: AgentG = None
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
            player=player, _solver=AgentG.from_page(page=page, tmp_dir=tmp_dir, **solver_opt)
        )

    @property
    def handle(self):
        return CommonHandler

    @property
    def promotions(self) -> List[Game]:
        self._promotions = self._promotions or get_promotions()
        return self._promotions

    async def _login(self, page: Page) -> str | None:
        async def insert_challenge(stage: Literal["email_exists_prod", "login_prod"]):
            fall_in_challenge = False

            for _ in range(15):
                if stage == "login_prod":
                    if not fall_in_challenge:
                        with suppress(TimeoutError):
                            await page.wait_for_url(URL_CART_SUCCESS, timeout=3000)
                            break
                        logger.debug("Attack challenge", stage=stage)
                elif stage == "email_exists_prod":
                    if not fall_in_challenge:
                        with suppress(TimeoutError):
                            await page.type("#password", "", timeout=3000)
                            break
                        logger.debug("Attack challenge", stage=stage)
                fall_in_challenge = True
                result = await self._solver.execute(window=stage)
                logger.debug("Parse result", stage=stage, result=result)
                match result:
                    case self._solver.status.CHALLENGE_BACKCALL:
                        await page.click("//a[@class='talon_close_button']")
                        await page.wait_for_timeout(1000)
                        await page.click("#sign-in", delay=200)
                    case self._solver.status.CHALLENGE_RETRY:
                        continue
                    case self._solver.status.CHALLENGE_SUCCESS:
                        if stage == "signin" and not self._solver.qr_queue.empty():
                            continue
                        with suppress(TimeoutError):
                            await page.wait_for_url(URL_CLAIM)
                            break
                        return

        await page.goto(URL_CLAIM, wait_until="domcontentloaded")
        if "false" == await page.locator("//egs-navigation").get_attribute("isloggedin"):
            await page.goto(URL_LOGIN, wait_until="domcontentloaded")
            logger.info("login-with-email", url=page.url)

            # {{< SIGN IN PAGE >}}
            await page.fill("#email", self.player.email)
            await page.click("//button[@aria-label='Continue']")

            # {{< INSERT CHALLENGE - email_exists_prod >}}
            await insert_challenge(stage="email_exists_prod")

            # {{< NESTED PAGE >}}
            await page.type("#password", self.player.password)
            await page.click("#sign-in")

            # {{< INSERT CHALLENGE - login_prod >}}
            await insert_challenge(stage="login_prod")

        logger.success("login", result="Successfully refreshed tokens")
        await page.goto(URL_CLAIM, wait_until="domcontentloaded")
        return self._solver.status.CHALLENGE_SUCCESS

    async def authorize(self, page: Page):
        for i in range(3):
            try:
                match await self._login(page):
                    case self._solver.status.CHALLENGE_SUCCESS:
                        return True
                    case _:
                        continue
            except TimeoutError:
                logger.warning("执行超时", task="authorize", retry=i)
                continue

        raise RuntimeError(f"Failed to flush token - agent={self.__class__.__name__}")

    async def flush_token(self, context: BrowserContext) -> Dict[str, str] | None:
        page = context.pages[0]
        await page.goto("https://www.epicgames.com/account/personal", wait_until="networkidle")
        await page.goto(
            "https://store.epicgames.com/zh-CN/p/orwell-keeping-an-eye-on-you",
            wait_until="networkidle",
        )
        await context.storage_state(path=self.player.ctx_cookie_path)
        cookies = self.player.ctx_cookies.reload(self.player.ctx_cookie_path)
        logger.success("flush_token", path=self.player.ctx_cookie_path)
        return cookies

    @retry(
        retry=retry_if_exception_type(TimeoutError),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(360) | stop_after_attempt(3)),
        reraise=True,
    )
    async def claim_weekly_games(self, page: Page, promotions: List[Game]):
        in_cart_nums = 0

        # --> Add promotions to Cart
        for promotion in promotions:
            logger.info("claim_weekly_games", action="go to store", url=promotion.url)
            await page.goto(promotion.url, wait_until="load")

            # <-- Handle pre-page
            with suppress(TimeoutError):
                await page.click("//button//span[text()='Continue']", timeout=3000)

            # --> Make sure promotion is not in the library before executing
            cta_btn = page.locator("//aside//button[@data-testid='add-to-cart-cta-button']")
            with suppress(TimeoutError):
                text = await cta_btn.text_content(timeout=10000)
                if text == "View In Cart":
                    in_cart_nums += 1
                    continue
                if text == "Add To Cart":
                    await cta_btn.click()
                    await expect(cta_btn).to_have_text("View In Cart")
                    in_cart_nums += 1

        if in_cart_nums == 0:
            logger.success("Pass claim task", reason="Free games not added to shopping cart")
            return

        # --> Goto cart page
        await page.goto(URL_CART, wait_until="domcontentloaded")
        await self.handle.empty_cart(page)
        await page.click("//button//span[text()='Check Out']")

        # <-- Handle Any LICENSE
        await self.handle.any_license(page)

        # --> Move to webPurchaseContainer iframe
        logger.info("claim_weekly_games", action="move to webPurchaseContainer iframe")
        wpc, payment_btn = await self.handle.move_to_purchase_container(page)
        logger.info("claim_weekly_games", action="click payment button")

        # <-- Handle UK confirm-order
        is_uk = await self.handle.uk_confirm_order(wpc)

        # <-- Insert challenge
        recur_url = URL_CART_SUCCESS
        await self.handle.insert_challenge(self._solver, page, wpc, payment_btn, recur_url, is_uk)

        # --> Wait for success
        await page.wait_for_url(recur_url)
        logger.success("claim_weekly_games", action="success", url=page.url)

        return True

    @retry(
        retry=retry_if_exception_type(TimeoutError),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(360) | stop_after_attempt(3)),
        reraise=True,
    )
    async def claim_bundle_games(self, page: Page, promotions: List[Game]):
        for promotion in promotions:
            logger.info("claim_bundle_games", action="go to store", url=promotion.url)
            await page.goto(promotion.url, wait_until="load")

            # <-- Handle pre-page
            with suppress(TimeoutError):
                await page.click("//button//span[text()='Continue']", timeout=3000)

            # --> Make sure promotion is not in the library before executing
            purchase_btn = page.locator("//button[@data-testid='purchase-cta-button']").first
            with suppress(TimeoutError):
                text = await purchase_btn.text_content(timeout=10000)
                if text == "Get":
                    await purchase_btn.click()
                    await page.wait_for_timeout(2000)
                else:
                    continue

            # <-- Handle Any LICENSE
            await self.handle.any_license(page)

            # --> Move to webPurchaseContainer iframe
            logger.info("claim_bundle_games", action="move to webPurchaseContainer iframe")
            wpc, payment_btn = await self.handle.move_to_purchase_container(page)
            logger.info("claim_bundle_games", action="click payment button")

            # <-- Handle UK confirm-order
            is_uk = await self.handle.uk_confirm_order(wpc)

            # <-- Insert challenge
            recur_url = f"https://store.epicgames.com/en-US/download?ns={promotion.namespace}&id={promotion.id}"
            await self.handle.insert_challenge(
                self._solver, page, wpc, payment_btn, recur_url, is_uk
            )

            # --> Wait for success
            await page.wait_for_url(recur_url)
            logger.success("claim_bundle_games", action="success", url=page.url)

            return True


def get_promotions() -> List[Game]:
    """
    获取周免游戏数据

    <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
    <本周免费> promotion["promotions"]["promotionalOffers"]
    :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
    """

    def _has_discount_target(prot: dict) -> bool | None:
        with suppress(KeyError, IndexError, TypeError):
            offers = prot["promotions"]["promotionalOffers"][0]["promotionalOffers"]
            for i, offer in enumerate(offers):
                if offer["discountSetting"]["discountPercentage"] == 0:
                    return True

    _promotions: List[Game] = []

    params = {"local": "zh-CN"}
    resp = httpx.get(URL_PROMOTIONS, params=params)
    try:
        data = resp.json()
    except JSONDecodeError as err:
        logger.error("Failed to get promotions", err=err)
    else:
        elements = data["data"]["Catalog"]["searchStore"]["elements"]
        promotions = [e for e in elements if e.get("promotions")]
        # Get store promotion data and <this week free> games
        for promotion in promotions:
            # Remove items that are discounted but not free.
            if not _has_discount_target(promotion):
                continue
            # package free games
            try:
                query = promotion["catalogNs"]["mappings"][0]["pageSlug"]
                promotion["url"] = f"{URL_PRODUCT_PAGE}{query}"
            except TypeError:
                promotion["url"] = f"{URL_PRODUCT_BUNDLES}{promotion['productSlug']}"
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
