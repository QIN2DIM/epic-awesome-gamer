# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description: 游戏商城控制句柄

import json
from contextlib import suppress
from json import JSONDecodeError
from typing import List

import httpx
from hcaptcha_challenger.agent import AgentV
from loguru import logger
from playwright.async_api import Page
from playwright.async_api import expect, TimeoutError, FrameLocator
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from models import OrderItem, Order
from models import PromotionGame
from settings import settings, RUNTIME_DIR

URL_CLAIM = "https://store.epicgames.com/en-US/free-games"
URL_LOGIN = (
    f"https://www.epicgames.com/id/login?lang=en-US&noHostRedirect=true&redirectUrl={URL_CLAIM}"
)
URL_CART = "https://store.epicgames.com/en-US/cart"
URL_CART_SUCCESS = "https://store.epicgames.com/en-US/cart/success"


URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
URL_PRODUCT_PAGE = "https://store.epicgames.com/en-US/p/"
URL_PRODUCT_BUNDLES = "https://store.epicgames.com/en-US/bundles/"


def get_promotions() -> List[PromotionGame]:
    """
    获取周免游戏数据

    <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
    <本周免费> promotion["promotions"]["promotionalOffers"]
    :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
    """

    def is_discount_game(prot: dict) -> bool | None:
        with suppress(KeyError, IndexError, TypeError):
            offers = prot["promotions"]["promotionalOffers"][0]["promotionalOffers"]
            for i, offer in enumerate(offers):
                if offer["discountSetting"]["discountPercentage"] == 0:
                    return True

    promotions: List[PromotionGame] = []

    resp = httpx.get(URL_PROMOTIONS, params={"local": "zh-CN"})

    try:
        data = resp.json()
    except JSONDecodeError as err:
        logger.error("Failed to get promotions", err=err)
        return []

    with suppress(Exception):
        cache_key = RUNTIME_DIR.joinpath("promotions.json")
        cache_key.parent.mkdir(parents=True, exist_ok=True)
        cache_key.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Get store promotion data and <this week free> games
    for e in data["data"]["Catalog"]["searchStore"]["elements"]:

        # Remove items that are discounted but not free.
        if not is_discount_game(e):
            continue

        # package free games
        try:
            e["url"] = f"{URL_PRODUCT_PAGE.rstrip('/')}/{e['offerMappings'][0]['pageSlug']}"
        except (KeyError, IndexError):
            if e.get("productSlug"):
                e["url"] = f"{URL_PRODUCT_BUNDLES.rstrip('/')}/{e['productSlug']}"
            else:
                logger.info(f"Failed to get URL: {e}")
                continue

        logger.info(e["url"])

        promotions.append(PromotionGame(**e))

    return promotions


class EpicAgent:

    def __init__(self, page: Page):
        self.page = page

        self.epic_games = EpicGames(self.page)

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
            logger.error("❌ context cookies is not available")
            return False

        # == 令牌有效 == #

        # 浏览器的身份信息仍然有效
        self._ctx_cookies_is_available = True

        # 加载正交的优惠商品数据
        await self._check_orders()

        # 促销列表为空，说明免费游戏都已收集，任务结束
        if not self._promotions:
            return True

        # 账号信息有效，但还存在没有领完的游戏
        return False

    async def collect_epic_games(self):
        if await self._should_ignore_task():
            logger.success("All week-free games are already in the library")
            return

        # 刷新浏览器身份信息
        if not self._ctx_cookies_is_available:
            return

        # 加载正交的优惠商品数据
        if not self._promotions:
            await self._check_orders()

        if not self._promotions:
            logger.success("All week-free games are already in the library")
            return

        game_promotions = []
        bundle_promotions = []
        for p in self._promotions:
            pj = json.dumps({"title": p.title, "url": p.url}, indent=2, ensure_ascii=False)
            logger.debug(f"Discover promotion \n{pj}")
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

        logger.debug("All tasks in the workflow have been completed")


class EpicGames:

    def __init__(self, page: Page):
        self.page = page

        self._promotions: List[PromotionGame] = []

    @staticmethod
    async def _agree_license(page: Page):
        logger.debug("Agree license")
        with suppress(TimeoutError):
            await page.click("//label[@for='agree']", timeout=4000)
            accept = page.locator("//button//span[text()='Accept']")
            if await accept.is_enabled():
                await accept.click()

    @staticmethod
    async def _active_purchase_container(page: Page):
        logger.debug("Move to webPurchaseContainer iframe")

        wpc = page.frame_locator("//iframe[@class='']")
        payment_btn = wpc.locator("//div[@class='payment-order-confirm']")
        with suppress(Exception):
            await expect(payment_btn).to_be_attached()
        await page.wait_for_timeout(2000)
        await payment_btn.click(timeout=6000)

        return wpc, payment_btn

    @staticmethod
    async def _uk_confirm_order(wpc: FrameLocator):
        logger.debug("UK confirm order")

        # <-- Handle UK confirm-order
        with suppress(TimeoutError):
            accept = wpc.locator(
                "//button[contains(@class, 'payment-confirm__btn payment-btn--primary')]"
            )
            if await accept.is_enabled(timeout=5000):
                await accept.click()
                return True

    @staticmethod
    async def add_promotion_to_cart(page: Page, urls: List[str]) -> bool:
        has_pending_free_promotion = False

        # --> Add promotions to Cart
        for url in urls:
            await page.goto(url, wait_until="load")

            # <-- Handle pre-page
            # with suppress(TimeoutError):
            #     await page.click("//button//span[text()='Continue']", timeout=3000)

            # 检查游戏是否已在库
            btn_list = page.locator("//aside//button")
            aside_btn_count = await btn_list.count()
            texts = ""
            for i in range(aside_btn_count):
                btn = btn_list.nth(i)
                btn_text_content = await btn.text_content()
                texts += btn_text_content

            if "In Library" in texts:
                logger.success(f"Already in the library - {url=}")
                continue

            add_to_cart_btn = page.locator(
                "//aside//button[@data-testid='add-to-cart-cta-button-pdp-sidebar']"
            )

            try:
                await expect(add_to_cart_btn).to_be_visible(timeout=10000)
                await expect(add_to_cart_btn).to_be_enabled(timeout=10000)
                await add_to_cart_btn.click()
                logger.debug(f"🙌 Add to the shopping cart - {url=}")
                has_pending_free_promotion = True

            except Exception as err:
                logger.warning(f"Failed to add promotion to cart - {err}")
                continue

        return has_pending_free_promotion

    async def _empty_cart(self, page: Page, wait_rerender: int = 30) -> bool | None:
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

            # Move paid games to the wishlist
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
                return await self._empty_cart(page, wait_rerender)
            return True
        except TimeoutError as err:
            logger.warning("Failed to empty shopping cart", err=err)
            return False

    async def _purchase_free_game(self):
        # == Cart Page == #
        await self.page.goto(URL_CART, wait_until="domcontentloaded")

        logger.debug("Move ALL paid games from the shopping cart out")
        await self._empty_cart(self.page)

        # {{< Insert hCaptcha Challenger >}}
        agent = AgentV(page=self.page, agent_config=settings)

        # --> Check out cart
        cart_buttons = self.page.locator("//button")
        cart_button_count = await cart_buttons.count()
        button_texts = []
        for i in range(cart_button_count):
            text = (await cart_buttons.nth(i).inner_text() or "").strip()
            if text:
                button_texts.append(text)
        logger.debug(f"Cart buttons: {button_texts}")

        checkout_btn = self.page.locator("//button[.//span[normalize-space()='Check Out']]")
        await expect(checkout_btn).to_be_visible(timeout=30000)
        await expect(checkout_btn).to_be_enabled(timeout=30000)
        await checkout_btn.click()

        # <-- Handle Any LICENSE
        await self._agree_license(self.page)

        try:
            # --> Move to webPurchaseContainer iframe
            logger.debug("Move to webPurchaseContainer iframe")
            wpc, payment_btn = await self._active_purchase_container(self.page)
            logger.debug("Click payment button")
            # <-- Handle UK confirm-order
            await self._uk_confirm_order(wpc)

            # {{< Active >}}
            await agent.wait_for_challenge()
        except Exception as err:
            logger.warning(f"Failed to solve captcha - {err}")
            await self.page.reload()
            return await self._purchase_free_game()

    @retry(retry=retry_if_exception_type(TimeoutError), stop=stop_after_attempt(2), reraise=True)
    async def collect_weekly_games(self, promotions: List[PromotionGame]):
        # --> Make sure promotion is not in the library before executing
        urls = [p.url for p in promotions]
        if not await self.add_promotion_to_cart(self.page, urls):
            logger.success("All week-free games are already in the library")
            return

        await self._purchase_free_game()

        try:
            await self.page.wait_for_url(URL_CART_SUCCESS)
            logger.success("🎉 Successfully collected all weekly games")
        except TimeoutError:
            logger.warning("Failed to collect all weekly games")
