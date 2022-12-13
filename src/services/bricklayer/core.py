# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import os
import re
import time
import typing
from contextlib import suppress
from hashlib import sha256
from urllib.request import getproxies

import hcaptcha_challenger as solver
import requests
from hcaptcha_challenger.exceptions import ChallengePassed
from loguru import logger
from playwright.sync_api import Error as NinjaError
from playwright.sync_api import Page, FrameLocator, BrowserContext
from playwright.sync_api import TimeoutError as NinjaTimeout

from services.settings import DIR_COOKIES, DIR_SCREENSHOT, DIR_USERS
from services.utils.toolbox import ToolBox
from .exceptions import UnableToGet, AuthMFA, AuthUnknownException, LoginException


class ArmorUtils:
    AUTH_SUCCESS = "success"
    AUTH_ERROR = "error"
    AUTH_CHALLENGE = "challenge"

    @staticmethod
    def fall_in_captcha_login(page: Page) -> typing.Optional[str]:
        """判断在登录时是否遇到人机挑战"""
        logger.info(">> ARMOR [ArmorUtils] 正在检测隐藏在登录界面的人机挑战...")
        flag = page.url

        for _ in range(15):
            # 控制台信息
            mui_typography = page.locator("//h6")
            with suppress(NinjaTimeout):
                mui_typography.first.wait_for(timeout=2000, state="attached")
                if mui_typography.count() > 1:
                    error_text = mui_typography.nth(1).text_content().strip()
                    logger.error(f">> ARMOR [ArmorUtils] 認證異常 - {error_text=}")
                    if "账号或密码" in error_text:
                        raise LoginException(error_text)
                    return ArmorUtils.AUTH_ERROR
            # 頁面重定向|跳過挑戰
            if page.url != flag:
                logger.info(">> ARMOR [ArmorUtils] 🥤 跳过人机挑战")
                return ArmorUtils.AUTH_SUCCESS
            # 多因素判斷
            page.wait_for_timeout(2000)
            with suppress(NinjaError):
                if page.locator(ArmorKnight.HOOK_CHALLENGE).is_visible():
                    return ArmorUtils.AUTH_CHALLENGE


class ArmorKnight(solver.HolyChallenger):
    """人机对抗模组"""

    # //iframe[@id='talon_frame_checkout_free_prod']
    HOOK_PURCHASE = "//div[@id='webPurchaseContainer']//iframe"
    HOOK_CHECKBOX = "//iframe[contains(@title, 'checkbox for hCaptcha')]"
    HOOK_CHALLENGE = "//iframe[contains(@title, 'hCaptcha挑战')]"

    def __init__(
        self, debug: typing.Optional[bool] = False, screenshot: typing.Optional[bool] = False
    ):
        super().__init__(debug=debug, screenshot=screenshot, lang="zh")
        self.critical_threshold = 3

    @property
    def utils(self):
        return ArmorUtils

    def get_label(self, frame_challenge: FrameLocator):
        try:
            self.prompt = frame_challenge.locator("//h2[@class='prompt-text']").text_content(
                timeout=10000
            )
        except NinjaTimeout:
            raise ChallengePassed("Man-machine challenge unexpectedly passed")

        _label = solver.HolyChallenger.split_prompt_message(self.prompt, self.lang)
        self.label = self.label_cleaning(_label)
        self.log(message="Get label", label=f"「{self.label}」")

    def download_images(self):
        # Initialize the challenge image download directory
        self.runtime_workspace = self._init_workspace()
        # Initialize the data container
        start = time.time()
        self.log("正在下载挑战图片")
        for alias_, url_ in self.alias2url.items():
            path_challenge_img_ = os.path.join(self.runtime_workspace, f"{alias_}.png")
            self.alias2path.update({alias_: path_challenge_img_})
            with open(path_challenge_img_, "wb") as file:
                file.write(requests.get(url_, proxies=getproxies()).content)
        self.log(message="Download challenge images", timeit=f"{round(time.time() - start, 2)}s")

    def mark_samples(self, frame_challenge: FrameLocator):
        """Get the download link and locator of each challenge image"""
        self.log("正在编排索引")
        samples = frame_challenge.locator("//div[@class='task-image']")
        count = samples.count()
        for i in range(count):
            sample = samples.nth(i)
            sample.wait_for()
            alias = sample.get_attribute("aria-label")
            image_style = sample.locator(".image").get_attribute("style")
            url = re.split(r'[(")]', image_style)[2]
            self.alias2url.update({alias: url})
            self.alias2locator.update({alias: sample})

    def challenge(self, frame_challenge: FrameLocator, model):
        ta = []
        # {{< IMAGE CLASSIFICATION >}}
        for alias in self.alias2path:
            with open(self.alias2path[alias], "rb") as file:
                data = file.read()
            t0 = time.time()
            result = model.solution(img_stream=data, label=self.label_alias[self.label])
            ta.append(time.time() - t0)
            if result:
                try:
                    self.alias2locator[alias].click(delay=100)
                except NinjaTimeout:
                    return

        # Check result of the challenge.
        if self.screenshot:
            _filename = f"{int(time.time())}.{model.flag}.{self.label_alias[self.label]}.png"
        #     self.captcha_screenshot(ctx, name_screenshot=_filename)

        # {{< SUBMIT ANSWER >}}
        with suppress(NinjaTimeout):
            frame_challenge.locator("//div[@class='button-submit button']").click(
                delay=1000, timeout=5000
            )
            self.log(message=f"Submit the challenge - {model.flag}: {round(sum(ta), 2)}s")

    def challenge_success(
        self,
        page: Page,
        frame_challenge: FrameLocator = None,
        window=None,
        init=True,
        hook_url=None,
        **kwargs,
    ) -> typing.Tuple[str, str]:
        """
        判断挑战是否成功的复杂逻辑
        :param hook_url:
        :param frame_challenge:
        :param init:
        :param window:
        :param page: 挑战者驱动上下文
        :return:
        """

        def is_continue_clickable():
            """ "
            False >>  dom elements hidden
            True >> it's clickable
            """
            try:
                prompts_obj = frame_challenge.locator("//div[@class='error-text']")
                prompts_obj.first.wait_for(timeout=2000)
                self.log("Checkout - status=再试一次")
                return True
            except NinjaTimeout:
                task_image = frame_challenge.locator("//div[@class='task-image']")
                task_image.first.wait_for(state="detached", timeout=3000)
                return False
            except NinjaError:
                return False

        def is_init_clickable():
            with suppress(NinjaError):
                return frame_challenge.locator("//div[@class='task-image']").first.is_visible()

        # 首轮测试后判断短时间内页内是否存在可点击的拼图元素
        # hcaptcha 最多两轮验证，一般情况下，账号信息有误仅会执行一轮，然后返回登录窗格提示密码错误
        # 其次是被识别为自动化控制，这种情况也是仅执行一轮，回到登录窗格提示“返回数据错误”
        if init and is_init_clickable():
            return self.CHALLENGE_CONTINUE, "继续挑战"
        if is_continue_clickable():
            return self.CHALLENGE_CONTINUE, "继续挑战"

        flag = page.url

        if window == "free":
            try:
                page.locator(self.HOOK_PURCHASE).wait_for(state="detached")
                return self.CHALLENGE_SUCCESS, "退火成功"
            except NinjaTimeout:
                return self.CHALLENGE_RETRY, "決策中斷"
        if window == "login":
            for _ in range(3):
                if hook_url:
                    with suppress(NinjaTimeout):
                        page.wait_for_url(hook_url, timeout=3000)
                        return self.CHALLENGE_SUCCESS, "退火成功"
                else:
                    page.wait_for_timeout(2000)
                    if page.url != flag:
                        if "id/login/mfa" not in page.url:
                            return self.CHALLENGE_SUCCESS, "退火成功"
                        raise AuthMFA("人机挑战已退出 - error=遭遇意外的 MFA 多重认证")

                mui_typography = page.locator("//h6")
                with suppress(NinjaTimeout):
                    mui_typography.first.wait_for(timeout=1000, state="attached")
                if mui_typography.count() > 1:
                    with suppress(AttributeError):
                        error_text = mui_typography.nth(1).text_content().strip()
                        if "错误回复" in error_text:
                            self.critical_threshold += 1
                            return self.CHALLENGE_RETRY, "登入页面错误回复"
                        if "there was a socket open error" in error_text:
                            return self.CHALLENGE_RETRY, "there was a socket open error"
                        if self.critical_threshold > 3:
                            logger.debug(f"認證失敗 - {error_text=}")
                            _unknown = AuthUnknownException(msg=error_text)
                            _unknown.report(error_text)
                            raise _unknown

    def anti_hcaptcha(
        self, page: Page, window: str = "login", recur_url=None
    ) -> typing.Union[bool, str]:
        """
        Handle hcaptcha challenge
        :param recur_url:
        :param window: [login free]
        :param page:
        :return:
        """
        if window == "login":
            frame_challenge = page.frame_locator(self.HOOK_CHALLENGE)
        else:
            frame_purchase = page.frame_locator(self.HOOK_PURCHASE)
            frame_challenge = frame_purchase.frame_locator(self.HOOK_CHALLENGE)

        try:
            # [👻] 人机挑战！
            for i in range(2):
                # [👻] 获取挑战标签
                self.get_label(frame_challenge)
                # [👻] 編排定位器索引
                self.mark_samples(frame_challenge)
                # [👻] 拉取挑戰圖片
                self.download_images()
                # [👻] 滤除无法处理的挑战类别
                if not self.label_alias.get(self.label):
                    path = (
                        f"datas/temp_cache/captcha_screenshot/{int(time.time())}.{self.label}.png"
                    )
                    page.screenshot(path=path)
                    return self.CHALLENGE_BACKCALL
                # [👻] 注册解决方案
                # 根据挑战类型自动匹配不同的模型
                model = self.switch_solution()
                # [👻] 識別|點擊|提交
                self.challenge(frame_challenge, model=model)
                # [👻] 輪詢控制臺響應
                with suppress(TypeError):
                    result, message = self.challenge_success(
                        page, frame_challenge, window=window, init=not i, hook_url=recur_url
                    )
                    self.log("获取响应", desc=f"{message}({result})")
                    if result in [
                        self.CHALLENGE_SUCCESS,
                        self.CHALLENGE_CRASH,
                        self.CHALLENGE_RETRY,
                    ]:
                        return result
                    page.wait_for_timeout(2000)
        # from::mark_samples url = re.split(r'[(")]', image_style)[2]
        except IndexError:
            page.evaluate("hcaptcha.getResponse()")
            return self.anti_hcaptcha(page, window, recur_url)


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
            fl = page.frame_locator(ArmorKnight.HOOK_PURCHASE)
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

    def __init__(self, email: str, password: str):
        """定义了一系列领取免费游戏所涉及到的浏览器操作。"""
        # 实体对象参数
        self.action_name = "BaseAction"
        self.email, self.password = email, password

        # 驱动参数
        self.loop_timeout = 300

        # 注册挑战者
        self.armor = self.armor or ArmorKnight(debug=True, screenshot=False)
        self.assert_util = AssertUtils()

    @property
    def utils(self):
        return self.assert_util

    # ======================================================
    # Reused Action Chains
    # ======================================================

    @staticmethod
    def _click_order_button(page: Page) -> typing.Optional[bool]:
        fl = page.frame_locator(ArmorKnight.HOOK_PURCHASE)
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
                    fl = page.frame_locator(ArmorKnight.HOOK_PURCHASE)
                    return fl.locator(ArmorKnight.HOOK_CHALLENGE).is_visible()
                return page.locator(ArmorKnight.HOOK_PURCHASE).is_visible()

        if fall_in_captcha_runtime():
            with suppress(ChallengePassed):
                resp = self.armor.anti_hcaptcha(page, window=window)
                self.captcha_runtime_memory(page, suffix=f"_{window}")
                return resp

    # ======================================================
    # Business Action Chains
    # ======================================================

    @staticmethod
    def captcha_runtime_memory(page: Page, suffix: str = ""):
        _finger = os.path.join(DIR_SCREENSHOT, f"{int(time.time())}{suffix}")
        page.screenshot(path=f"{_finger}.png")
        with open(f"{_finger}.mhtml", "w", newline="", encoding="utf8") as file:
            file.write(page.content())

    def login(self, email: str, password: str, page: Page, auth_str: str):
        """作为被动方式，登陆账号，刷新 identity token"""
        logger.info(f">> MATCH [{self.action_name}] 刷新令牌")
        if auth_str == "games":
            url_store = "https://store.epicgames.com/zh-CN/"
            url_claim = self.URL_FREE_GAMES
            url_login = f"https://www.epicgames.com/id/login?lang=zh-CN&noHostRedirect=true&redirectUrl={url_claim}"
            try:
                page.goto(url_store, wait_until="domcontentloaded")
                page.goto(url_claim, wait_until="load")
            except NinjaTimeout:
                page.reload(wait_until="domcontentloaded")
            with suppress(NinjaTimeout):
                sign_text = page.locator("//span[contains(@class, 'sign-text')]").text_content()
                if sign_text != "登录":
                    logger.info(f">> MATCH [{self.action_name}] 持久化信息未过期")
                    return ArmorUtils.AUTH_SUCCESS
        else:
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
                    return ArmorUtils.AUTH_SUCCESS

        page.goto(url_login, wait_until="networkidle")
        if page.url == url_claim:
            return ArmorUtils.AUTH_SUCCESS
        page.click("#login-with-epic", delay=200)
        page.type("#email", email, delay=100)
        page.type("#password", password, delay=110)
        page.click("#sign-in", delay=200)
        logger.info(f">> MATCH [{self.action_name}] 实体信息注入完毕")

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
        fl_purchase = page.frame_locator(ArmorKnight.HOOK_PURCHASE)
        fl_challenge = fl_purchase.frame_locator(ArmorKnight.HOOK_CHALLENGE)
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

    def __init__(self, auth_str: typing.Literal["games", "unreal"], email: str, password: str):
        super().__init__(email=email, password=password)

        self.action_name = "CookieManager"
        self.auth_str = auth_str
        self.path_ctx_cookies = os.path.join(DIR_COOKIES, f"{self._t()}.json")
        self.user_data_dir = os.path.join(DIR_USERS, self._t())
        self.ctx_session = None
        self._ctx_cookies = None

    def _t(self) -> str:
        return (
            sha256(f"{self.email[-3::-1]}{self.auth_str}".encode("utf-8")).hexdigest()
            if self.email
            else "ctx_cookies"
        )

    @property
    def hash(self):
        return self._t()

    def load_ctx_cookies(self) -> typing.Optional[typing.List[dict]]:
        """载入本地缓存的身份令牌"""
        if not os.path.exists(self.path_ctx_cookies):
            return []
        with open(self.path_ctx_cookies, "r", encoding="utf8") as file:
            data: dict = json.load(file)
        ctx_cookies = data.get("cookies", []) if isinstance(data, dict) else []
        if not ctx_cookies:
            return []

        logger.info(f">> LOAD [{self.action_name}] Load context cookie")
        self._ctx_cookies = ctx_cookies
        return self._ctx_cookies

    @property
    def ctx_cookies(self):
        return self._ctx_cookies

    @property
    def has_available_token(self):
        return self._is_available_token()

    def _is_available_token(self, ctx_cookies: typing.Optional[typing.List[dict]] = None) -> bool:
        """检测 Cookie 是否有效"""
        if cookies := ctx_cookies or self.load_ctx_cookies():
            _kwargs = {
                "headers": {
                    "cookie": ToolBox.transfer_cookies(cookies),
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                    " Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.42",
                    "origin": "https://www.epicgames.com",
                    "referer": "https://www.epicgames.com/",
                },
                "proxies": getproxies(),
                "allow_redirects": False,
            }
            response = requests.get(self.URL_ACCOUNT_PERSONAL, **_kwargs)
            return response.status_code == 200
        return False

    def refresh_ctx_cookies(self, context: BrowserContext) -> typing.Optional[bool]:
        """更新上下文身份信息，若认证数据过期则弹出 login 任务更新令牌。"""
        logger.info(">> MATCH [__context__] 🎮启动挑战者上下文")
        recur_url = self.URL_FREE_GAMES if self.auth_str == "games" else self.URL_UNREAL_MONTH

        page = context.new_page()
        balance_operator = -1
        while balance_operator < 8:
            balance_operator += 1
            # Enter the account information and jump to the man-machine challenge page.
            result = self.login(self.email, self.password, page=page, auth_str=self.auth_str)
            # Assert if you are caught in a man-machine challenge.
            if result not in [ArmorUtils.AUTH_SUCCESS]:
                result = ArmorUtils.fall_in_captcha_login(page)
            # Skip Challenge.
            if result == ArmorUtils.AUTH_SUCCESS:
                return True
            # Winter is coming, so hear me roar!
            elif result == ArmorUtils.AUTH_CHALLENGE:
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
