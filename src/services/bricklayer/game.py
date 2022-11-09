# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing
from contextlib import suppress

from loguru import logger
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as NinjaTimeout

from .core import EpicAwesomeGamer, CookieManager
from .exceptions import AuthException, UnableToGet


class GameClaimer(EpicAwesomeGamer):
    """性能更高的调度策略"""

    URL_GAME_CART = "https://store.epicgames.com/zh-CN/cart"

    def __init__(self, email: str, password: str, silence: bool = None):
        super().__init__(email=email, password=password)
        self.result = ""
        self.silence = True if silence is None else silence
        self.promotion_url2state = {}
        self.promotion_url2title = {}

        self.action_name = "GameClaimer"
        self.cookie_manager = CookieManager(auth_str="games", email=email, password=password)

    def cart_balancing(self, page: Page):
        """
        购物车|愿望清单的内容转移

        1. 查看购物车是否为空
        2. 将<付费内容>&&<后置资源>移至愿望清单

        <后置资源>：必须购置游戏本体才能获取的 DLC 附加内容。
        购物车中存在<后置资源>且缺少先决条件时无法下单

        # -----------------------------------------------
        # len(assert_obj)!=0
        # -----------------------------------------------
        # 存在<后置资源>且缺少先决条件
        # -----------------------------------------------
        assert_obj = tree.xpath("//div[@data-component='AlertMessage']")
        if len(assert_obj) != 0:
            # 将<后置资源>移至愿望清单
            print("存在<后置资源>且缺少先决条件")
        # -----------------------------------------------
        # len(free_cards) / 2 == len(offer_cards)
        # -----------------------------------------------
        # 购物车中均为免费商品，否则存在付费内容
        # -----------------------------------------------
        offer_cards = tree.xpath("//div[@data-component='OfferCardLayout']")
        free_cards = tree.xpath("//span[text()='免费']")
        if len(free_cards) / 2 != len(offer_cards):
            # 将<付费内容>移至愿望清单
            print("存在付费内容")
        :return:
        """
        logger.debug(f">> REMOVE [{self.action_name}] 将购物车商品移至愿望清单")
        page.goto(self.URL_GAME_CART)
        move_buttons = page.locator("//span[text()='移至愿望清单']")
        with suppress(NinjaTimeout):
            move_buttons.last.wait_for(timeout=2000)
        for i in range(move_buttons.count()):
            move_buttons.nth(i).click(delay=200)

    def empty_shopping_payment(self, page: Page):
        """清空购物车"""
        for i in range(3):
            page.goto(self.URL_GAME_CART)
            if self.cart_is_empty(page):
                logger.success(f"ADVANCE [{self.action_name}] ✔ 购物车已清空")
                break
            if page.locator("//span[text()='移至愿望清单']").first.is_visible():
                page.click("//span[text()='下单']/parent::button")
                logger.info("[🔖] 已激活购物车零元购订单")
            # [🚀] 新用户首次购买游戏需要处理许可协议书
            if not i and self.assert_util.surprise_license(page):  # mode: add
                continue
            # [🚀] 处理游戏订单
            self.cart_handle_payment(page)  # mode: add

    def purchase_status(self, page: Page, page_link: str, title: str) -> typing.Optional[str]:
        """
        断言当前上下文页面的游戏的在库状态。

        :param title:
        :param page_link:
        :param page:
        :return:
        """
        page.wait_for_load_state(timeout=60000)

        # 捕获按钮对象，根据按钮上浮动的提示信息断言游戏在库状态 超时的空对象主动抛出异常
        for _ in range(5):
            try:
                purchase_button = page.locator("//button[@data-testid='purchase-cta-button']")
                purchase_button.first.wait_for(state="visible", timeout=2000)
                break
            except NinjaTimeout:
                if "再进行一步操作" in page.content():
                    return self.assert_util.ONE_MORE_STEP
        else:
            return self.assert_util.ASSERT_OBJECT_EXCEPTION

        state2result = {"获取": self.assert_util.GAME_PENDING, "已在库中": self.assert_util.GAME_CLAIM}
        # 游戏状态 在库|获取|购买|即将推出
        purchase_msg = purchase_button.text_content()
        logger.debug(
            f">> Checkout [{self.action_name}] {title} - state={purchase_msg} link={page_link}"
        )
        for state in state2result:
            if state in purchase_msg:
                return state2result[state]
        return purchase_msg

    def get_free_game(
        self, page_link: str, page: Page, pattern: typing.Literal["get", "add"]
    ) -> typing.Optional[str]:
        """获取周免资源 游戏本体/附加内容 集成接口"""
        for i in range(3):
            page.goto(page_link)

            # ------ {{< 检查游戏在库状态 | [GET/ADD] >}} ------
            # 当游戏不处于 待认领 状态时跳过任务
            # ------------------------------------------------
            self.assert_util.surprise_warning_purchase(page)
            self.result = self.purchase_status(
                page=page, page_link=page_link, title=self.promotion_url2title[page_link]
            )
            self.promotion_url2state[page_link] = self.result
            if self.result == self.assert_util.ASSERT_OBJECT_EXCEPTION:
                continue
            if self.result != self.assert_util.GAME_PENDING:
                break
            # ------ {{< DONE >}} ------

            # ------ {{< 上下文切换 | [GET/ADD] >}} ------
            self.captcha_runtime_memory(page, suffix="_switch")
            if pattern == self.CLAIM_MODE_ADD:
                with suppress(NinjaTimeout):
                    page.wait_for_load_state(state="networkidle")
                page.locator("//button[@data-testid='add-to-cart-cta-button']").first.click()
                logger.info("[🔖] 已添加商品至购物车")
                return self.result
            if pattern == self.CLAIM_MODE_GET:
                page.click("//button[@data-testid='purchase-cta-button']")
                logger.info("[🔖] 已激活商品页零元购订单")
                # [🚀] 新用户首次购买游戏需要处理许可协议书
                if not i and self.assert_util.surprise_license(page):  # mode: get
                    continue
                # [🚀] 处理游戏订单
                self.cart_handle_payment(page)  # mode: get
                page.wait_for_timeout(2000)
            # ------ {{< DONE >}} ------

        return self.result


def empower_games_claimer(
    claimer: GameClaimer, page_link: str, page: Page, pattern: typing.Literal["get", "add"]
) -> typing.Optional[str]:
    """获取周免资源 游戏本体/附加内容 集成接口"""
    action_name = claimer.action_name
    try:
        return claimer.get_free_game(page_link=page_link, page=page, pattern=pattern)
    except UnableToGet as error:
        logger.debug(f">> QUIT [{action_name}] {str(error).strip()} - {page_link=}")
        return claimer.assert_util.GAME_LIMIT
    except AuthException as error:
        logger.critical(f">> SKIP [{action_name}] {error.msg}")
