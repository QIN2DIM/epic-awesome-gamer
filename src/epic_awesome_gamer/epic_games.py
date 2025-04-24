# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import json
import os
from contextlib import suppress
from pathlib import Path
from typing import List, Dict

from hcaptcha_challenger.agent import AgentConfig, AgentV
from hcaptcha_challenger.models import RequestType, CaptchaResponse
from loguru import logger
from playwright.async_api import BrowserContext, expect, TimeoutError, Page, FrameLocator, Locator
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import *

from epic_awesome_gamer.types import PromotionGame

# fmt:off
URL_CLAIM = "https://store.epicgames.com/en-US/free-games"
URL_LOGIN = f"https://www.epicgames.com/id/login?lang=en-US&noHostRedirect=true&redirectUrl={URL_CLAIM}"
URL_CART = "https://store.epicgames.com/en-US/cart"
URL_CART_SUCCESS = "https://store.epicgames.com/en-US/cart/success"
# fmt:on


class EpicSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    cache_dir: Path = Path("tmp/.cache")

    EPIC_EMAIL: str = Field(
        default_factory=lambda: os.getenv("EPIC_EMAIL"),
        description="Epic 游戏账号，需要关闭多步验证",
    )
    EPIC_PASSWORD: SecretStr = Field(
        default_factory=lambda: os.getenv("EPIC_PASSWORD"),
        description=" Epic 游戏密码，需要关闭多步验证",
    )
    APPRISE_SERVERS: str | None = Field(
        default="", description="System notification by Apprise\nhttps://github.com/caronc/apprise"
    )


class EpicGames:

    def __init__(self, page: Page, settings: EpicSettings):
        self.page = page
        self.settings = settings
        self._promotions: List[PromotionGame] = []

    @staticmethod
    async def _any_license(page: Page):
        with suppress(TimeoutError):
            await page.click("//label[@for='agree']", timeout=2000)
            accept = page.locator("//button//span[text()='Accept']")
            if await accept.is_enabled():
                await accept.click()

    @staticmethod
    async def _move_to_purchase_container(page: Page):
        wpc = page.frame_locator("//iframe[@class='']")
        payment_btn = wpc.locator("//div[@class='payment-order-confirm']")
        with suppress(Exception):
            await expect(payment_btn).to_be_attached()
        await page.wait_for_timeout(2000)
        await payment_btn.click(timeout=6000)

        return wpc, payment_btn

    @staticmethod
    async def _uk_confirm_order(wpc: FrameLocator):
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
    async def _insert_challenge(
        self, page: Page, wpc: FrameLocator, payment_btn: Locator, recur_url: str, is_uk: bool
    ):
        response = await solver.execute(window="free")
        logger.debug("task done", sattus=f"{solver.status.CHALLENGE_SUCCESS}")

        match response:
            case solver.status.CHALLENGE_BACKCALL | solver.status.CHALLENGE_RETRY:
                await wpc.locator("//a[@class='talon_close_button']").click()
                await page.wait_for_timeout(1000)
                if is_uk:
                    await self._uk_confirm_order(wpc)
                await payment_btn.click(delay=200)
            case solver.status.CHALLENGE_SUCCESS:
                await page.wait_for_url(recur_url)
                return

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
                return await self._empty_cart(page, wait_rerender)
            return True
        except TimeoutError as err:
            logger.warning("Failed to empty shopping cart", err=err)
            return False

    async def authorize(self, page: Page):
        await page.goto(URL_CLAIM, wait_until="domcontentloaded")
        if "false" == await page.locator("//egs-navigation").get_attribute("isloggedin"):
            await page.goto(URL_LOGIN, wait_until="domcontentloaded")
            logger.debug(f"Login with Email - {page.url}")

            agent_config = AgentConfig(ignore_request_types=[RequestType.IMAGE_DRAG_DROP])
            agent = AgentV(page=page, agent_config=agent_config)

            # {{< SIGN IN PAGE >}}
            await page.type("#email", self.settings.EPIC_EMAIL)
            await page.type("#password", self.settings.EPIC_PASSWORD.get_secret_value())
            await page.click("#sign-in")

            # await page.click("//a[@class='talon_close_button']")
            await agent.wait_for_challenge()

            if agent.cr_list:
                cr: CaptchaResponse = agent.cr_list[-1]
                print(json.dumps(cr.model_dump(by_alias=True), indent=2, ensure_ascii=False))

        logger.success("Login")
        await page.goto(URL_CART, wait_until="domcontentloaded")

        return True

    @staticmethod
    async def flush_token(
        context: BrowserContext, *, path: Path | str = None
    ) -> Dict[str, str] | None:
        page = context.pages[0]
        await page.goto("https://www.epicgames.com/account/personal", wait_until="networkidle")
        await page.goto(
            "https://store.epicgames.com/zh-CN/p/orwell-keeping-an-eye-on-you",
            wait_until="networkidle",
        )
        storage_state = await context.storage_state(path=path)
        return {ck["name"]: ck["value"] for ck in storage_state["cookies"]}

    @retry(
        retry=retry_if_exception_type(TimeoutError),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(360) | stop_after_attempt(3)),
        reraise=True,
    )
    async def collect_weekly_games(self, page: Page, promotions: List[PromotionGame]):
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
        await self._empty_cart(page)
        await page.click("//button//span[text()='Check Out']")

        # <-- Handle Any LICENSE
        await self._any_license(page)

        # --> Move to webPurchaseContainer iframe
        logger.info("claim_weekly_games", action="move to webPurchaseContainer iframe")
        wpc, payment_btn = await self._move_to_purchase_container(page)
        logger.info("claim_weekly_games", action="click payment button")

        # <-- Handle UK confirm-order
        is_uk = await self._uk_confirm_order(wpc)

        # <-- Insert challenge
        recur_url = URL_CART_SUCCESS
        await self._insert_challenge(self._solver, page, wpc, payment_btn, recur_url, is_uk)

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
    async def collect_bundle_games(self, page: Page, promotions: List[PromotionGame]):
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
            await self._any_license(page)

            # --> Move to webPurchaseContainer iframe
            logger.info("claim_bundle_games", action="move to webPurchaseContainer iframe")
            wpc, payment_btn = await self._move_to_purchase_container(page)
            logger.info("claim_bundle_games", action="click payment button")

            # <-- Handle UK confirm-order
            is_uk = await self._uk_confirm_order(wpc)

            # <-- Insert challenge
            recur_url = f"https://store.epicgames.com/en-US/download?ns={promotion.namespace}&id={promotion.id}"
            await self._insert_challenge(self._solver, page, wpc, payment_btn, recur_url, is_uk)

            # --> Wait for success
            await page.wait_for_url(recur_url)
            logger.success("claim_bundle_games", action="success", url=page.url)

            return True
