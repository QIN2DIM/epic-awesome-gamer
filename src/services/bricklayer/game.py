# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing

from loguru import logger
from playwright.sync_api import Page

from .core import EpicAwesomeGamer, CookieManager
from .exceptions import AuthException, UnableToGet


class GameClaimer(EpicAwesomeGamer):
    """性能更高的调度策略"""

    URL_GAME_CART = "https://store.epicgames.com/zh-CN/cart"

    # 促销实体 任务结果
    promotion2result = None

    def __init__(self, email: str, password: str, silence: bool = None, claim_mode: str = None):
        super().__init__(email=email, password=password)
        self.result = ""
        self.silence = True if silence is None else silence
        self.promotion2result = self.promotion2result or {}

        if claim_mode not in [self.CLAIM_MODE_ADD, self.CLAIM_MODE_GET]:
            self.claim_mode = self.CLAIM_MODE_ADD
        else:
            self.claim_mode = claim_mode

        self.action_name = "GameClaimer"
        self.cookie_manager = CookieManager(
            auth_str=self.AUTH_STR_GAMES, email=email, password=password
        )

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
        count = move_buttons.count()
        for i in range(count):
            move_buttons.nth(i).click()

    def empty_shopping_payment(self, page: Page):
        """清空购物车"""
        for i in range(3):
            page.goto(self.URL_GAME_CART)
            if self.cart_is_empty(page):
                logger.success(f"ADVANCE [{self.action_name}] ✔ 购物车已清空")
                break
            self._activate_payment(page, mode=self.ACTIVE_BINGO)
            # [🚀] 新用户首次购买游戏需要处理许可协议书
            if not i and self.assert_.surprise_license(page):
                continue
            # [🚀] 处理游戏订单
            self.cart_handle_payment(page)

    def get_free_game(self, page_link: str, page: Page) -> typing.Optional[str]:
        """获取周免资源 游戏本体/附加内容 集成接口"""
        for i in range(2):
            page.goto(page_link)
            # [🚀] 处理前置的遮挡信息
            self.assert_.surprise_warning_purchase(page)
            # [🚀] 断言游戏的在库状态
            self.result = self.assert_.purchase_status(
                page=page,
                page_link=page_link,
                get=bool(self.claim_mode == self.CLAIM_MODE_GET),
                promotion2url=self.promotion2result,
                action_name=self.action_name,
                init=not i,
            )
            # 当游戏不处于 待认领 状态时跳过后续业务
            if self.result != self.assert_.GAME_PENDING:
                # <游戏状态断言超时>或<检测到异常的实体对象>
                # 在超时阈值内尝试重新拉起服务
                if self.result == self.assert_.ASSERT_OBJECT_EXCEPTION:
                    continue
                # 否则游戏状态处于<领取成功>或<已在库>或<付费游戏>
                self.promotion2result.update({page_link: self.result})
                return self.result
            # [🚀] 激活游戏订单或将促销实体加入购物车
            self._activate_payment(page, mode=self.claim_mode)

            # ------ {{< 上下文切换 | [GET/ADD] >}} ------
            self.captcha_runtime_memory(page, suffix="_switch")
            if self.claim_mode == self.CLAIM_MODE_ADD:
                return self.result
            # ------ {{< DONE >}} ------

        return self.result


def empower_games_claimer(claimer: GameClaimer, page_link: str, page: Page) -> typing.Optional[str]:
    """获取周免资源 游戏本体/附加内容 集成接口"""
    action_name = claimer.action_name
    try:
        return claimer.get_free_game(page_link=page_link, page=page)
    except UnableToGet as error:
        logger.debug(f">> QUIT [{action_name}] {str(error).strip()} - {page_link=}")
        return claimer.assert_.GAME_LIMIT
    except AuthException as error:
        logger.critical(f">> SKIP [{action_name}] {error.msg}")
