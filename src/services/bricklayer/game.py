# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import time
import typing

from loguru import logger

from services.utils.toolbox import ToolBox
from .core import EpicAwesomeGamer, CookieManager
from .exceptions import (
    AssertTimeout,
    SwitchContext,
    PaymentBlockedWarning,
    AuthException,
    UnableToGet,
    CookieExpired,
    PaymentAutoSubmit,
)


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

    def cart_balancing(self, ctx_cookies: typing.List[dict], ctx_session, init=True):
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
        _message = "将购物车商品移至愿望清单" if init else "正在审核移动操作"
        logger.debug(
            ToolBox.runtime_report(motive="REMOVE", action_name=self.action_name, message=_message)
        )
        self._reset_page(
            ctx=ctx_session,
            ctx_cookies=ctx_cookies,
            page_link=self.URL_GAME_CART,
            auth_str=self.AUTH_STR_GAMES,
        )
        self._move_product_to_wishlist(ctx=ctx_session)

    def empty_shopping_payment(self, ctx_cookies: typing.List[dict], ctx_session):
        """清空购物车"""
        _loop_start = time.time()
        init = True
        try:
            while True:
                # [🚀] 重载身份令牌
                logger.debug("[🛵] 重载身份令牌")
                self._reset_page(
                    ctx=ctx_session,
                    ctx_cookies=ctx_cookies,
                    page_link=self.URL_GAME_CART,
                    auth_str=self.AUTH_STR_GAMES,
                )

                # [🚀] 激活游戏订单
                logger.debug("[🛵] 审查购物车状态")
                if "购物车是空的" in ctx_session.page_source:
                    logger.success(
                        ToolBox.runtime_report(
                            motive="ADVANCE", action_name=self.action_name, message="✔ 购物车已清空"
                        )
                    )
                    break
                resp = self._activate_payment(ctx_session, mode=self.ACTIVE_BINGO, init_cart=init)
                if not init and not resp:
                    logger.success(
                        ToolBox.runtime_report(
                            motive="ADVANCE", action_name=self.action_name, message="✔ 购物车已清空"
                        )
                    )
                    break

                # [🚀] 新用户首次购买游戏需要处理许可协议书
                if init and self.assert_.surprise_license(ctx_session):
                    logger.debug("[🛵] 新用户首次购买游戏需要处理许可协议书")
                    ctx_session.refresh()
                    continue

                # [🚀] 处理游戏订单
                logger.debug("[🛵] 处理购物订单...")
                self.cart_handle_payment(ctx_session)

                # [🚀] 更新上下文状态
                init = False
                self.assert_.timeout(_loop_start, self.loop_timeout)
        except AssertTimeout:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT", action_name=self.action_name, message="循环断言超时，任务退出。"
                )
            )

    def get_free_game(
        self, page_link: str, ctx_cookies: typing.List[dict], ctx
    ) -> typing.Optional[str]:
        """获取周免资源 游戏本体/附加内容 集成接口"""
        if not ctx_cookies:
            raise CookieExpired(self.assert_.COOKIE_EXPIRED)

        _loop_start = time.time()
        init = True
        while True:
            # [🚀] 重载身份令牌
            # InvalidCookieDomainException：需要 2 次 GET 重载 cookie relative domain
            # InvalidCookieDomainException：跨域认证，访问主域名或过滤异站域名信息
            self._reset_page(
                ctx=ctx, page_link=page_link, ctx_cookies=ctx_cookies, auth_str=self.AUTH_STR_GAMES
            )

            # [🚀] 处理前置的遮挡信息
            self.assert_.surprise_warning_purchase(ctx)

            # [🚀] 断言游戏的在库状态
            # 捕获 ONE MORE STEP CHALLENGE
            for _ in range(2):
                self.result = self.assert_.purchase_status(
                    ctx=ctx,
                    page_link=page_link,
                    get=bool(self.claim_mode == self.CLAIM_MODE_GET),
                    promotion2url=self.promotion2result,
                    action_name=self.action_name,
                    init=init,
                )
                if self.result != self.assert_.ONE_MORE_STEP:
                    break
                if self.armor.utils.face_the_checkbox(ctx) and self.armor.anti_checkbox(ctx):
                    self._duel_with_challenge(ctx, window="oms")
                    time.sleep(5)
            else:
                self.assert_.timeout(_loop_start, self.loop_timeout)
                continue

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
            self._activate_payment(ctx, mode=self.claim_mode)

            # ------ {{< 上下文切换 | [GET/ADD] >}} ------
            self.captcha_runtime_memory(ctx, suffix="_switch")
            if self.claim_mode == self.CLAIM_MODE_ADD:
                break
            # ------ {{< DONE >}} ------

            # [🚀] 新用户首次购买游戏需要处理许可协议书
            if self.assert_.surprise_license(ctx):
                ctx.refresh()
                continue

            # [🚀] 订单消失
            if self.assert_.payment_auto_submit(ctx):
                continue

            # [🚀] 处理游戏订单
            self._handle_payment(ctx)

            # [🚀] 更新上下文状态
            init = False
            self.assert_.timeout(_loop_start, self.loop_timeout)

        return self.result


def claim_stabilizer(
    game_claimer: GameClaimer,
    page_link: str,
    ctx_cookies: typing.List[dict],
    ctx_session,
    get_blocked_warning=None,
) -> typing.Optional[str]:
    """获取周免资源 游戏本体/附加内容 集成接口"""
    action_name = game_claimer.action_name
    try:
        return game_claimer.get_free_game(
            page_link=page_link, ctx_cookies=ctx_cookies, ctx=ctx_session
        )
    except AssertTimeout:
        logger.debug(
            ToolBox.runtime_report(motive="QUIT", action_name=action_name, message="循环断言超时，任务退出。")
        )
    except UnableToGet as error:
        logger.debug(
            ToolBox.runtime_report(
                motive="QUIT", action_name=action_name, message=str(error).strip(), url=page_link
            )
        )
        return game_claimer.assert_.GAME_LIMIT
    except SwitchContext as error:
        logger.warning(
            ToolBox.runtime_report(
                motive="SWITCH",
                action_name=action_name,
                message="正在退出标准上下文",
                error=str(error).strip(),
                url=page_link,
            )
        )
    except PaymentAutoSubmit:
        pass
    except PaymentBlockedWarning as error:
        logger.debug(
            ToolBox.runtime_report(
                motive="QUIT",
                action_name=action_name,
                message="🚧 订单异常",
                type=f"PaymentException {error}".strip(),
                url=page_link,
            )
        )
        if get_blocked_warning:
            raise PaymentBlockedWarning from error
    except AuthException as error:
        logger.critical(
            ToolBox.runtime_report(motive="SKIP", action_name=action_name, message=error.msg)
        )
