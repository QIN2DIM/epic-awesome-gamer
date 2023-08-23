# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing
from contextlib import suppress

from hcaptcha_challenger.agents.exceptions import ChallengePassed
from loguru import logger
from playwright.sync_api import Error as NinjaError
from playwright.sync_api import Page, BrowserContext
from playwright.sync_api import TimeoutError as NinjaTimeout

from services.agents.hcaptcha_solver import AuStatus, Radagon, is_fall_in_captcha
from services.bricklayer.exceptions import UnableToGet


class AssertUtils:
    """处理穿插在认领过程中意外出现的遮挡信息"""

    # 特征指令/简易错误
    # 此部分状态作为消息模板的一部分，尽量简短易理解
    COOKIE_EXPIRED = "💥 饼干过期了"
    ASSERT_OBJECT_EXCEPTION = "🚫 无效的断言对象"
    GAME_OK = "🎮 已在库"
    GAME_PENDING = "👀 待认领"
    GAME_CLAIM = "🛒 领取成功"
    GAME_NOT_FREE = "🦽 付费游戏"
    GAME_LIMIT = "👻 地區限制"
    ONE_MORE_STEP = "🥊 进位挑战"
    GAME_FAILED = "🦄 领取失败"

    @staticmethod
    def surprise_license(page: Page) -> typing.Optional[bool]:
        """新用户首次购买游戏需要处理许可协议书"""
        surprise_obj = page.locator("//label[@for='agree']")
        if not surprise_obj.is_visible():
            return
        logger.debug("[🛵] 新用户首次购买游戏需要处理许可协议书")
        if surprise_obj.text_content() == "我已阅读并同意最终用户许可协议书":
            page.click("#agree")
            page.click("//span[text()='接受']/parent::button")
            return True

    @staticmethod
    def surprise_warning_purchase(page: Page) -> typing.Optional[bool]:
        """处理弹窗遮挡消息"""
        try:
            page.locator("//h1").first.wait_for(timeout=3000, state="visible")
        except NinjaTimeout:
            return True
        else:
            surprise_warning_objs = page.locator("//h1//span")
            for i in range(surprise_warning_objs.count()):
                text = surprise_warning_objs.nth(i).text_content()
                if "内容品当前在您所在平台或地区不可用。" in text:
                    raise UnableToGet("内容品当前在您所在平台或地区不可用。")
                if "本游戏包含成人内容" in text:
                    page.click("//span[text()='继续']/parent::button")
                    return True
            return False

    @staticmethod
    def purchase_status(
        page: Page,
        page_link: str,
        get: bool,
        promotion2url: typing.Dict[str, str],
        action_name: typing.Optional[str] = "AssertUtils",
        init: typing.Optional[bool] = True,
    ) -> typing.Optional[str]:
        """
        断言当前上下文页面的游戏的在库状态。

        :param promotion2url:
        :param get:
        :param init:
        :param action_name:
        :param page_link:
        :param page:
        :return:
        """
        page.wait_for_load_state(state="load")

        # 捕获按钮对象，根据按钮上浮动的提示信息断言游戏在库状态 超时的空对象主动抛出异常
        for _ in range(5):
            try:
                purchase_button = page.locator("//button[@data-testid='purchase-cta-button']")
                purchase_button.first.wait_for(state="visible", timeout=2000)
                break
            except NinjaTimeout:
                if "再进行一步操作" in page.content():
                    return AssertUtils.ONE_MORE_STEP
        else:
            return AssertUtils.ASSERT_OBJECT_EXCEPTION

        # 游戏名 超时的空对象主动抛出异常
        game_name = promotion2url.get(page_link)
        # 游戏状态 在库|获取|购买
        purchase_msg = purchase_button.text_content()
        if "已在" in purchase_msg:
            _message = "🛴 游戏已在库" if init else "🥂 领取成功"
            logger.info(f">> GET [{action_name}] {_message} - game=『{game_name}』")
            return AssertUtils.GAME_OK if init else AssertUtils.GAME_CLAIM
        if "获取" in purchase_msg:
            try:
                deadline = page.text_content("//span[contains(text(),'优惠截止于')]", timeout=500)
            except NinjaTimeout:
                deadline = ""
            if init:
                message = f"🚀 正在为玩家领取免费游戏 {deadline}" if get else f"🛒 添加至购物车 {deadline}"
                logger.success(f">> GET [{action_name}] {message} - game=『{game_name}』")
            return AssertUtils.GAME_PENDING
        if "购买" in purchase_msg:
            logger.warning(f">> SKIP [{action_name}] 🚧 这不是免费游戏 - game=『{game_name}』")
            return AssertUtils.GAME_NOT_FREE
        return AssertUtils.ASSERT_OBJECT_EXCEPTION

    @staticmethod
    def refund_info(page: Page):
        """处理订单中的 退款及撤销权信息"""
        with suppress(NinjaTimeout):
            fl = page.frame_locator(Radagon.HOOK_PURCHASE)
            agree_button = fl.locator("//span[text()='我同意']/ancestor::button")
            agree_button.click(timeout=2000)
            logger.debug("[🍜] 处理 UK 地区账号的「退款及撤销权信息」。")

    @staticmethod
    def unreal_surprise_license(page: Page):
        with suppress(NinjaTimeout):
            page.click("//span[text()='我已阅读并同意《最终用户许可协议》']", timeout=2000)
            page.click("//span[text()='接受']")
            logger.info("处理首次下单的许可协议")


class EpicAwesomeGamer:
    """白嫖人的基础设施"""

    # 操作对象参数
    URL_ACCOUNT_PERSONAL = "https://www.epicgames.com/account/personal"
    URL_FREE_GAMES = "https://store.epicgames.com/zh-CN/free-games"

    # 购物车结算成功
    URL_CART_SUCCESS = "https://store.epicgames.com/zh-CN/cart/success"

    URL_UNREAL_STORE = "https://www.unrealengine.com/marketplace/zh-CN/assets"
    URL_UNREAL_MONTH = (
        f"{URL_UNREAL_STORE}?count=20&sortBy=currentPrice&sortDir=ASC&start=0&tag=4910"
    )

    CLAIM_MODE_ADD = "add"
    CLAIM_MODE_GET = "get"
    ACTIVE_BINGO = "下单"

    # Talon Service Challenger
    armor = None

    def __init__(self):
        """定义了一系列领取免费游戏所涉及到的浏览器操作。"""
        # 实体对象参数
        self.action_name = "BaseAction"

        # 驱动参数
        self.loop_timeout = 300

        # 注册挑战者
        self.armor = self.armor or Radagon()
        self.assert_util = AssertUtils()

    # ======================================================
    # Reused Action Chains
    # ======================================================

    @staticmethod
    def _click_order_button(page: Page) -> typing.Optional[bool]:
        fl = page.frame_locator(Radagon.HOOK_PURCHASE)
        payment_btn = fl.locator("//button[contains(@class,'payment-btn')]")
        with suppress(NinjaTimeout):
            page.click("#onetrust-accept-btn-handler", timeout=2000)
        with suppress(NinjaTimeout):
            page.click("//span[text()='继续']/parent::button", timeout=3000)
        payment_btn.click()
        return True

    def _duel_with_challenge(self, page: Page, window="free") -> typing.Optional[bool]:
        """
        动态处理人机挑战
        :return: True挑战成功，False挑战失败/需要跳过，None其他信号
        """

        def fall_in_captcha_runtime():
            with suppress(NinjaError):
                if window == "free":
                    fl = page.frame_locator(Radagon.HOOK_PURCHASE)
                    return fl.locator(Radagon.HOOK_CHALLENGE).is_visible()
                return page.locator(Radagon.HOOK_PURCHASE).is_visible()

        if fall_in_captcha_runtime():
            with suppress(ChallengePassed):
                resp = self.armor.anti_hcaptcha(page, window=window)
                return resp

    # ======================================================
    # Business Action Chains
    # ======================================================

    def _login_unreal(self, page: Page):
        url_claim = self.URL_UNREAL_MONTH
        url_login = f"https://www.unrealengine.com/id/login?lang=zh_CN&redirectUrl={url_claim}"
        try:
            page.goto(url_claim)
        except NinjaTimeout:
            page.reload(wait_until="domcontentloaded")
        with suppress(NinjaTimeout):
            sign_text = page.locator("//span[contains(@class, 'user-label')]").text_content()
            if sign_text != "登录":
                logger.info(f">> MATCH [{self.action_name}] 持久化信息未过期")
                return AuStatus.AUTH_SUCCESS
        page.goto(url_login)
        if page.url == url_claim:
            return AuStatus.AUTH_SUCCESS
        page.click("#login-with-epic")
        page.fill("#email", self.player.epic_email)
        page.fill("#password", self.player.epic_password)
        page.click("#sign-in")

    def _login_game(self, page: Page):
        url_claim = "https://store.epicgames.com/en-US/free-games"
        url_login = f"https://www.epicgames.com/id/login?lang=zh-CN&noHostRedirect=true&redirectUrl={url_claim}"

        page.goto(url_claim, wait_until="domcontentloaded")
        while page.locator('a[role="button"]:has-text("Sign In")').count() > 0:
            logger.info("login", mode="game")
            page.goto(url_login, wait_until="domcontentloaded")
            page.click("#login-with-epic")
            page.fill("#email", self.player.epic_email)
            page.fill("#password", self.player.epic_password)
            page.click("#sign-in")
            page.wait_for_url(url_claim)
        return AuStatus.AUTH_SUCCESS

    def login(self, page: Page, auth_str: str):
        """作为被动方式，登陆账号，刷新 identity token"""
        logger.info("尝试刷新令牌", action=self.action_name)
        if auth_str == "games":
            result = self._login_game(page)
        else:
            # FIXME: Unreliable
            result = self._login_unreal(page)

        logger.info("玩家信息注入完毕", action=self.action_name)
        return result

    @staticmethod
    def cart_is_empty(page: Page):
        logger.debug("[🛵] 审查购物车状态")
        spans = page.locator("//span")
        count = spans.count()
        for i in range(count):
            with suppress(NinjaTimeout):
                if "空的" in spans.nth(i).text_content(timeout=1000):
                    return True

    def cart_success(self, page: Page, times: int = 0):
        """
        提高跳过人机挑战的期望，使用轮询的方式检测运行状态
        确保进入此函数时，已经点击 order 按钮，并已处理欧盟和新手协议，无任何遮挡。
        """
        if times >= 2:
            return False
        with suppress(NinjaTimeout):
            page.wait_for_url(self.URL_CART_SUCCESS, timeout=1000)
            logger.debug("[🎃] 退火成功")
            return True
        fl_purchase = page.frame_locator(Radagon.HOOK_PURCHASE)
        fl_challenge = fl_purchase.frame_locator(Radagon.HOOK_CHALLENGE)
        with suppress(NinjaTimeout):
            fl_challenge.locator(".prompt-text").wait_for(state="visible", timeout=1000)
            return self.cart_success(page, times + 1)

    def cart_handle_payment(self, page: Page):
        logger.debug("[🛵] 处理购物订单...")
        if self._click_order_button(page):  # cart_handle_payment
            self.assert_util.refund_info(page)  # cart_handle_payment
            if not self.cart_success(page):
                logger.debug("[⚔] 捕获隐藏在订单中的人机挑战...")
                self._duel_with_challenge(page)  # cart_handle_payment
            logger.debug("[🌀] 弹出内联订单框架...")
            return True

    def unreal_activate_payment(self, page: Page, init=True):
        """从虚幻商店购物车激活订单"""
        page.goto(self.URL_UNREAL_MONTH)
        # =======================================================
        # [🍜] 清空购物车，确保仅添加免费商品
        # =======================================================
        if page.locator(".cart-amount").text_content() != "0":
            page.click("//div[@class='shopping-cart']")
            remove_buttons = page.locator(".remove")
            remove_buttons.first.wait_for()
            for _ in range(remove_buttons.count()):
                remove_buttons.first.wait_for()
                remove_buttons.first.click()
            page.click("//div[@class='shopping-cart']")
        # =======================================================
        # [🍜] 将月供内容添加到购物车
        # =======================================================
        in_library_tags = page.locator("//span[text()='撰写评论']").count()
        all_free_tags = page.locator("//span[@class='asset-discount-percentage']").count()
        if in_library_tags >= all_free_tags:
            return AssertUtils.GAME_OK if init else AssertUtils.GAME_CLAIM
        else:
            offer_tags = page.locator("//div[@class='asset-list-group']//article")
            for i in range(offer_tags.count()):
                offer_tag = offer_tags.nth(i)
                offer_name = offer_tag.locator("//h3//a").text_content()
                offer_button = offer_tag.locator("//i").first
                is_free = offer_tag.locator(
                    "//span[@class='asset-discount-percentage']"
                ).is_visible()
                # If it is free offer, and you haven't received it yet
                if is_free and offer_button.is_visible():
                    offer_button.click(delay=500)
                    logger.debug(f">> ADD [{self.action_name}] 添加到购物车 - offer=『{offer_name}』")

        # =======================================================
        # [🍜] 正在清空购物车
        # =======================================================
        logger.debug(f">> HANDLE [{self.action_name}] 激活购物车")
        page.click("//div[@class='shopping-cart']")

        logger.debug(f">> HANDLE [{self.action_name}] 激活订单")
        page.click("//button[text()='去支付']")

        # =======================================================
        # [🍜] 处理首次下单的许可协议
        # =======================================================
        self.assert_util.unreal_surprise_license(page)

        return AssertUtils.GAME_PENDING

    def unreal_handle_payment(self, page: Page):
        # [🍜] Click the [order] button
        self._click_order_button(page)  # unreal
        # [🍜] 处理 UK 地区账号的「退款及撤销权信息」
        self.assert_util.refund_info(page)  # unreal
        # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
        self._duel_with_challenge(page)  # unreal


class CookieManager(EpicAwesomeGamer):
    """管理上下文身份令牌"""

    def __init__(self, auth_str: typing.Literal["games", "unreal"]):
        super().__init__()
        self.auth_str = auth_str

    def refresh_ctx_cookies(self, context: BrowserContext) -> typing.Optional[bool]:
        """更新上下文身份信息，若认证数据过期则弹出 login 任务更新令牌。"""
        logger.info(">> MATCH [__context__] 🎮启动挑战者上下文")
        recur_url = self.URL_FREE_GAMES if self.auth_str == "games" else self.URL_UNREAL_MONTH

        page = context.new_page()
        balance_operator = -1
        while balance_operator < 8:
            balance_operator += 1
            # Enter the account information and jump to the man-machine challenge page.
            result = self.login(page=page, auth_str=self.auth_str)
            # Assert if you are caught in a man-machine challenge.
            if result not in [AuStatus.AUTH_SUCCESS]:
                result = is_fall_in_captcha(page)
            # Skip Challenge.
            if result == AuStatus.AUTH_SUCCESS:
                return True
            # Winter is coming, so hear me roar!
            elif result == AuStatus.AUTH_CHALLENGE:
                resp = self.armor.anti_hcaptcha(page, window="login", recur_url=recur_url)
                if resp == self.armor.CHALLENGE_SUCCESS:
                    return True
                elif resp == self.armor.CHALLENGE_REFRESH:
                    balance_operator -= 0.5
                elif resp == self.armor.CHALLENGE_BACKCALL:
                    balance_operator -= 0.75
                elif resp == self.armor.CHALLENGE_CRASH:
                    balance_operator += 0.5
        logger.critical(f">> MISS [{self.action_name}] Identity token update failed")
        return False
