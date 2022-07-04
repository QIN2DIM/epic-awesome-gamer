# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import time
from typing import List, Optional, Dict, Union

from lxml import etree  # skipcq: BAN-B410 - Ignore credible sources

from services.settings import logger, SynergyTunnel
from services.utils import ToolBox
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

    def __init__(self, silence: bool = None, claim_mode: str = None):
        super().__init__()
        self.silence = True if silence is None else silence

        if claim_mode not in [self.CLAIM_MODE_ADD, self.CLAIM_MODE_GET]:
            self.claim_mode = self.CLAIM_MODE_ADD
        else:
            self.claim_mode = claim_mode

        self.action_name = "GameClaimer"
        self.cookie_manager = CookieManager(auth_str=self.AUTH_STR_GAMES)

    def has_attach(self, content: bytes = None, tree=None) -> Optional[str]:
        """检测当前游戏商品是否有DLC urlIn游戏页"""
        tree = etree.HTML(content) if tree is None else tree
        dlc_tag = tree.xpath(
            "//li[@data-component='PDPTertiaryNavigation']//a[contains(@href,'dlc')]"
        )
        if not dlc_tag:
            return
        dlc_page = (
            f"{self.URL_MASTER_HOST}{dlc_tag[0].attrib.get('href')}?"
            f"sortBy=relevancy&sortDir=DESC&priceTier=tierFree&count=40&start=0"
        )
        return dlc_page

    @staticmethod
    def has_free_dlc(content: bytes = None, tree=None) -> bool:
        """检测游戏是否有免费DLC urlIn附加内容筛选免费内容页"""
        tree = etree.HTML(content) if tree is None else tree
        if tree.xpath("//span[text()='未找到结果']"):
            return False
        return True

    def parse_free_dlc_details(self, url, status_code, content=None, tree=None):
        dlc_tree = etree.HTML(content) if tree is None else tree

        # [🚀] 获取当前商品所有免费DLC链接
        dlc_tags: list = dlc_tree.xpath("//div[@data-component='DiscoverCard']//a")
        dlc_details = {}

        # [📝] 获取DLC基础信息
        for tag in dlc_tags:
            aria_label = tag.attrib.get("aria-label")
            try:
                name = aria_label.split(",")[0]
            except (IndexError, AttributeError):
                name = url.split("/")[-1]

            # 部分地区账号会被重定向至附加内容的默认页面
            # 此页面未触发筛选器，混杂着付费/免费的附加内容
            # 重新判断当前游戏的状态，清洗付费游戏
            is_free = True
            try:
                if "tierFree" not in url or status_code == 302:
                    is_free = aria_label.split(",")[-1].strip() == "0"
            except (IndexError, AttributeError):
                pass

            if is_free:
                url = f"{self.URL_MASTER_HOST}{tag.attrib.get('href')}"
                dlc_detail = {"url": url, "name": name, "dlc": True}
                dlc_details.update({url: dlc_detail})

        # [🚀] 清洗返回值使之符合接口规则
        return list(dlc_details.values())

    def get_free_dlc_details(self, ctx_url: str, cookie: str) -> List[Dict[str, Union[str, bool]]]:
        """
        1. 检测一个游戏实体是否存在免费附加内容
        2. 将可领取的免费附加内容编织成任务对象并返回
        3. 一个游戏实体可能存在多个可领取的免费DLC
        :param ctx_url: 游戏本体商城链接
        :param cookie:
        :return: [{"url": url of dlc, "name": name of dlc, "dlc": True}, ... ]
        """
        # [🚀] 检测当前商品是否有DLC
        tree, response = ToolBox.handle_html(ctx_url, cookie)
        dlc_page = self.has_attach(tree=tree)
        if not dlc_page:
            return []

        # [🚀] 检测当前商品是否有免费的DLC
        dlc_tree, response = ToolBox.handle_html(dlc_page, cookie)
        if not self.has_free_dlc(tree=dlc_tree):
            return []

        # [🚀] 获取当前商品所有免费DLC链接
        return self.parse_free_dlc_details(dlc_page, response.status_code, tree=dlc_tree)

    def is_empty_cart(self, ctx_cookies: List[dict], init=True) -> Optional[bool]:
        """判断商城购物车是否为空"""
        cookie = ToolBox.transfer_cookies(ctx_cookies)
        tree, resp_ = ToolBox.handle_html(self.URL_GAME_CART, cookie)

        assert_obj = tree.xpath("//span[text()='您的购物车是空的。']")
        if len(assert_obj) != 0:
            if not init:
                logger.success(
                    ToolBox.runtime_report(
                        motive="ADVANCE", action_name=self.action_name, message="✔ 购物车已清空"
                    )
                )
            return True
        if "challengeTitle" in resp_.text:
            return None
        return False

    def cart_balancing(self, ctx_cookies: List[dict], ctx_session, init=True):
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

    def empty_shopping_payment(self, ctx_cookies: List[dict], ctx_session):
        """清空购物车"""
        _loop_start = time.time()
        init = True
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

    def get_free_game(self, page_link: str, ctx_cookies: List[dict], ctx) -> Optional[str]:
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
            get = bool(self.claim_mode == self.CLAIM_MODE_GET)
            for _ in range(2):
                self.result = self.assert_.purchase_status(
                    ctx, page_link, get, self.action_name, init
                )
                if self.result != self.assert_.ONE_MORE_STEP:
                    break
                if self.armor.face_the_checkbox(ctx) and self.armor.anti_checkbox(ctx):
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
                SynergyTunnel.set_combat(page_link, self.result)
                break

            # [🚀] 激活游戏订单
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

    def claim_booster(self, ctx_cookies: List[dict], ctx_session):
        try:
            return self.empty_shopping_payment(ctx_cookies=ctx_cookies, ctx_session=ctx_session)
        except AssertTimeout:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT", action_name=self.action_name, message="循环断言超时，任务退出。"
                )
            )

    def claim_stabilizer(
        self, page_link: str, ctx_cookies: List[dict], ctx_session, get_blocked_warning=None
    ) -> Optional[str]:
        """获取周免资源 游戏本体/附加内容 集成接口"""
        try:
            return self.get_free_game(page_link=page_link, ctx_cookies=ctx_cookies, ctx=ctx_session)
        except AssertTimeout:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT", action_name=self.action_name, message="循环断言超时，任务退出。"
                )
            )
        except UnableToGet as error:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT",
                    action_name=self.action_name,
                    message=str(error).strip(),
                    url=page_link,
                )
            )
        except SwitchContext as error:
            logger.warning(
                ToolBox.runtime_report(
                    motive="SWITCH",
                    action_name=self.action_name,
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
                    action_name=self.action_name,
                    message="🚧 订单异常",
                    type=f"PaymentException {error}".strip(),
                    url=page_link,
                )
            )
            if get_blocked_warning:
                raise PaymentBlockedWarning from error
        except AuthException as error:
            logger.critical(
                ToolBox.runtime_report(
                    motive="SKIP", action_name=self.action_name, message=error.msg
                )
            )
