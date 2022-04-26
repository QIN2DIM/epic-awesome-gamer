# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import asyncio
import os
import sys
import time
from hashlib import sha256
from typing import List, Optional, NoReturn

import cloudscraper
import yaml
from selenium.common.exceptions import (
    TimeoutException,
    ElementNotVisibleException,
    WebDriverException,
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    InvalidCookieDomainException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from services.settings import (
    logger,
    DIR_COOKIES,
    DIR_CHALLENGE,
    DIR_MODEL,
    EPIC_EMAIL,
    EPIC_PASSWORD,
    PATH_RAINBOW,
)
from services.utils import (
    YOLO,
    sk_recognition,
    ToolBox,
    ArmorCaptcha,
    SubmitException,
    AshFramework,
    ChallengeReset,
    get_challenge_ctx,
    ChallengeTimeout,
    ChallengerContext,
)
from .exceptions import (
    AssertTimeout,
    UnableToGet,
    SwitchContext,
    PaymentBlockedWarning,
    AuthException,
    PaymentAutoSubmit,
    AuthMFA,
    AuthUnknownException,
    CookieRefreshException,
)

# 显示人机挑战的DEBUG日志
ARMOR_DEBUG = True


class ArmorUtils(ArmorCaptcha):
    """人机对抗模组"""

    AUTH_SUCCESS = "success"
    AUTH_ERROR = "error"
    AUTH_CHALLENGE = "challenge"

    CHALLENGE_SUCCESS = "success"
    CHALLENGE_CONTINUE = "continue"
    CHALLENGE_CRASH = "crash"
    CHALLENGE_RETRY = "retry"
    CHALLENGE_REFRESH = "refresh"

    # //iframe[@id='talon_frame_checkout_free_prod']
    HOOK_CHALLENGE = "//iframe[contains(@title,'content')]"
    HOOK_PURCHASE = "//div[@id='webPurchaseContainer']//iframe"

    def __init__(self, debug: bool = ARMOR_DEBUG):
        super().__init__(dir_workspace=DIR_CHALLENGE, debug=debug)

        # 重定向工作空间
        self.model = YOLO(DIR_MODEL)
        self.critical_threshold = 2

    @staticmethod
    def fall_in_captcha_login(ctx: ChallengerContext) -> Optional[str]:
        """
        判断在登录时是否遇到人机挑战

        :param ctx:
        :return: True：已进入人机验证页面，False：跳转到个人主页
        """
        flag_ = ctx.current_url

        logger.debug(
            ToolBox.runtime_report(
                action_name="ArmorUtils", motive="ARMOR", message="正在检测隐藏在登录界面的人机挑战..."
            )
        )

        ctx.switch_to.default_content()
        for _ in range(55):
            # {{< 檢測控制臺的附加信號 >}}
            try:
                mui_typography = ctx.find_elements(By.TAG_NAME, "h6")
                if len(mui_typography) > 1:
                    error_text = mui_typography[1].text.strip()
                    logger.error(
                        ToolBox.runtime_report(
                            action_name="ArmorUtils",
                            motive="ARMOR",
                            message="認證異常",
                            error_text=error_text,
                        )
                    )
                    raise AssertTimeout
            except (WebDriverException, AttributeError, TypeError):
                pass

            # {{< 頁面重定向|跳過挑戰 >}}
            try:
                WebDriverWait(ctx, 1).until(EC.url_changes(flag_))
                logger.debug(
                    ToolBox.runtime_report(
                        action_name="ArmorUtils", motive="ARMOR", message="🥤 跳过人机挑战"
                    )
                )
                return ArmorUtils.AUTH_SUCCESS
            except TimeoutException:
                pass

            # {{< 多因素判斷 >}}
            # 僅當前置條件滿足時，挑戰框架可見性斷言結果才有效
            try:
                WebDriverWait(ctx, 1, 0.1).until_not(
                    EC.element_to_be_clickable((By.ID, "sign-in"))
                )
            except TimeoutException:
                continue
            else:
                # {{< 挑戰框架可見 >}}
                try:
                    WebDriverWait(ctx, 1, 0.1).until(
                        EC.visibility_of_element_located(
                            (By.XPATH, ArmorUtils.HOOK_CHALLENGE)
                        )
                    )
                    return ArmorUtils.AUTH_CHALLENGE
                except TimeoutException:
                    pass
        assert AssertTimeout

    @staticmethod
    def fall_in_captcha_runtime(ctx: ChallengerContext) -> Optional[bool]:
        """
        判断在下单时是否遇到人机挑战

        # "//div[@id='talon_frame_checkout_free_prod']"
        :param ctx:
        :return:
        """
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, ArmorUtils.HOOK_CHALLENGE))
            )
            return True
        except TimeoutException:
            return False

    def switch_challenge_iframe(self, ctx: ChallengerContext):
        WebDriverWait(ctx, 5).until(
            EC.frame_to_be_available_and_switch_to_it((By.XPATH, self.HOOK_CHALLENGE))
        )

    def switch_solution(self, mirror, label: Optional[str] = None):
        """模型卸载"""
        label = self.label if label is None else label

        if label in ["垂直河流"]:
            return sk_recognition.RiverChallenger(path_rainbow=PATH_RAINBOW)
        if label in ["天空中向左飞行的飞机"]:
            return sk_recognition.DetectionChallenger(path_rainbow=PATH_RAINBOW)
        if label in ["请选择天空中所有向右飞行的飞机"]:
            return sk_recognition.RightPlane(path_rainbow=PATH_RAINBOW)

        return mirror

    def download_images(self) -> None:
        """
        植入协程框架加速下载。

        :return:
        """

        class ImageDownloader(AshFramework):
            """协程助推器 提高挑战图片的下载效率"""

            def __init__(self, docker=None):
                super().__init__(docker=docker)

            async def control_driver(self, context, session=None):
                path_challenge_img, url = context

                # 下载挑战图片
                async with session.get(url) as response:
                    with open(path_challenge_img, "wb") as file:
                        file.write(await response.read())

        self.log(message="下载挑战图片")

        # 初始化挑战图片下载目录
        workspace_ = self._init_workspace()

        # 初始化数据容器
        docker_ = []
        for alias_, url_ in self.alias2url.items():
            path_challenge_img_ = os.path.join(workspace_, f"{alias_}.png")
            self.alias2path.update({alias_: path_challenge_img_})
            docker_.append((path_challenge_img_, url_))

        # 启动最高功率的协程任务
        if sys.platform.startswith("win") or "cygwin" in sys.platform:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(ImageDownloader(docker=docker_).subvert(workers="fast"))
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                ImageDownloader(docker=docker_).subvert(workers="fast")
            )

        self.runtime_workspace = workspace_

    def challenge_success(
        self, ctx: ChallengerContext, init: bool = True, **kwargs
    ) -> Optional[str]:
        """
        判断挑战是否成功的复杂逻辑

        IF index is True:
        经过首轮识别点击后，出现四种结果：
        - 直接通过验证（小概率）
        - 进入第二轮（正常情况）
          通过短时间内可否继续点击拼图来断言是否陷入第二轮测试
        - 要求重试（小概率）
          特征被识别或网络波动，需要重试
        - 通过验证，弹出 2FA 双重认证
          无法处理，任务结束

        :param ctx: 挑战者驱动上下文
        :param init: 是否为初次挑战
        :return:
        """

        def is_challenge_image_clickable():
            try:
                WebDriverWait(ctx, 3).until_not(
                    EC.element_to_be_clickable((By.XPATH, "//div[@class='task-image']"))
                )
                return False
            except TimeoutException:
                return True

        door: str = kwargs.get("door", "login")
        flag = ctx.current_url

        # 首轮测试后判断短时间内页内是否存在可点击的拼图元素
        # hcaptcha 最多两轮验证，一般情况下，账号信息有误仅会执行一轮，然后返回登录窗格提示密码错误
        # 其次是被识别为自动化控制，这种情况也是仅执行一轮，回到登录窗格提示“返回数据错误”
        if is_challenge_image_clickable():
            return self.CHALLENGE_CONTINUE

        try:
            WebDriverWait(ctx, 2, 0.1).until(
                EC.visibility_of_element_located((By.XPATH, "//div[@class='error-text']"))
            )
            return self.CHALLENGE_RETRY
        except TimeoutException:
            if door == "free":
                for _ in range(200):
                    ctx.switch_to.default_content()
                    try:
                        ctx.switch_to.frame(
                            ctx.find_element(By.XPATH, ArmorUtils.HOOK_PURCHASE)
                        )
                        time.sleep(0.1)
                    except NoSuchElementException:
                        return self.CHALLENGE_SUCCESS
            if door == "login":
                # {{< 人機挑戰|模擬退火 >}}
                ctx.switch_to.default_content()
                for _ in range(45):
                    # 主動彈出挑戰框架 輪詢控制台回應
                    mui_typography = ctx.find_elements(By.TAG_NAME, "h6")

                    # {{< 檢測錯誤回復 >}}
                    # 1. 賬號信息錯誤 | 賬號被鎖定
                    # 2. 高威脅水平的訪客IP
                    if len(mui_typography) > 1:
                        try:
                            error_text = mui_typography[1].text
                        except AttributeError:
                            pass
                        else:
                            if "错误回复" in error_text:
                                self.critical_threshold -= 1
                                if self.critical_threshold == 0:
                                    self.log("原子實例被檢測", resp=error_text)
                                    raise CookieRefreshException(error_text)
                                return self.CHALLENGE_CRASH
                            else:
                                self.log("認證失敗", resp=error_text)
                                _unknown = AuthUnknownException()
                                _unknown.report(error_text)
                                raise _unknown
                    # {{< 輪詢漏檢狀態 >}}
                    # 1. 回到挑戰框架 查看是否有漏檢挑戰項目
                    # 2. 檢測鏈接跳轉
                    else:
                        # {{< FluentAPI 判斷頁面跳轉 >}}
                        # 1. 如果没有遇到多重认证，人机挑战成功
                        # 2. 人机挑战通过，但可能还需处理 `2FA` 问题（超纲了）
                        try:
                            WebDriverWait(ctx, 0.5).until(EC.url_changes(flag))
                        except TimeoutException:
                            pass
                        else:
                            if "id/login/mfa" not in ctx.current_url:
                                return self.CHALLENGE_SUCCESS
                            raise AuthMFA("人机挑战已退出 error=遭遇意外的 2FA 双重认证")

                # 輪詢超時 若此時頁面仍未跳轉視爲挑戰失敗
                if ctx.current_url == flag:
                    if door == "login":
                        self.log("断言超时，挑战继续")
                    return self.CHALLENGE_CONTINUE

    def anti_hcaptcha(
        self, ctx: ChallengerContext, door: str = "login"
    ) -> Optional[bool]:  # noqa
        """
        Handle hcaptcha challenge

        ## Reference

        M. I. Hossen and X. Hei, "A Low-Cost Attack against the hCaptcha System," 2021 IEEE Security
        and Privacy Workshops (SPW), 2021, pp. 422-431, doi: 10.1109/SPW53761.2021.00061.

        > ps:该篇文章中的部分内容已过时，现在 hcaptcha challenge 远没有作者说的那么容易应付。

        # Output sessionId
        # print(ctx.find_elements(By.TAG_NAME, "p")[1].text)

        :param door: [login free]
        :param ctx:
        :return:
        """
        # [👻] 进入人机挑战关卡
        self.switch_challenge_iframe(ctx)

        # [👻] 人机挑战！
        try:
            for index in range(10):
                self.log(f"<enter[{index}]>".center(50, "="))

                # [👻] 获取挑战图片
                self.get_label(ctx)
                if self.tactical_retreat():
                    ctx.switch_to.default_content()
                    self.log("獲取響應", resp=self.CHALLENGE_REFRESH)
                    self.log(f"<quit[{index}]>".center(50, "="))
                    return False

                # [👻] 注册解决方案
                # 根据挑战类型自动匹配不同的模型
                model = self.switch_solution(mirror=self.model)

                # [👻] 編排定位器索引
                self.mark_samples(ctx)

                # [👻] 拉取挑戰圖片
                self.download_images()

                # [👻] 識別|點擊|提交
                self.challenge(ctx, model=model)

                # [👻] 輪詢控制臺響應
                result = self.challenge_success(ctx, init=not bool(index), door=door)
                self.log("獲取響應", resp=result)
                self.log(f"<quit[{index}]>".center(50, "="))

                ctx.switch_to.default_content()
                if result in [self.CHALLENGE_CONTINUE, self.CHALLENGE_RETRY]:
                    self.switch_challenge_iframe(ctx)
                    continue
                if result == self.CHALLENGE_SUCCESS:
                    return True
                if result == self.CHALLENGE_CRASH:
                    return False
        # 提交结果断言超时或 mark_samples() 等待超时
        except (WebDriverException, SubmitException):
            ctx.switch_to.default_content()
            return False


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

    @staticmethod
    def login_error(ctx: ChallengerContext) -> bool:
        """登录失败 可能原因为账号或密码错误"""

        threshold_timeout = 3
        start = time.time()

        while True:
            # "任务超时：网络响应过慢"
            if time.time() - start > threshold_timeout:
                return False

            # 提交按钮正在响应或界面弹出人机挑战
            try:
                submit_button = ctx.find_element(By.ID, "sign-in")
                status_obj = submit_button.get_attribute("tabindex")
                if status_obj == "-1":
                    continue
            except (AttributeError, WebDriverException):
                pass

            # 登录页面遭遇 Alert，可能原因为：
            # - 账号或密码无效；
            # - Auth Response 异常；
            # - 账号被锁定；
            try:
                h6_tags = ctx.find_elements(By.TAG_NAME, "h6")
                if len(h6_tags) > 1:
                    return True
                return False
            except NoSuchElementException:
                pass

    @staticmethod
    def get_login_error_msg(ctx) -> Optional[str]:
        """获取登录页面的错误信息"""
        try:
            return ctx.find_element(By.XPATH, "//form//h6").text.strip()
        except (WebDriverException, AttributeError):
            return "null"

    @staticmethod
    def wrong_driver(ctx, msg: str):
        """判断当前上下文任务是否使用了错误的浏览器驱动"""
        if "chrome.webdriver" in str(ctx.__class__):
            raise SwitchContext(msg)

    @staticmethod
    def surprise_license(ctx: ChallengerContext) -> Optional[bool]:
        """新用户首次购买游戏需要处理许可协议书"""
        try:
            surprise_obj = WebDriverWait(
                ctx, 3, ignored_exceptions=ElementNotVisibleException
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//label//span[@data-component='Message']")
                )
            )
        except TimeoutException:
            return
        else:
            try:
                if surprise_obj.text == "我已阅读并同意最终用户许可协议书":
                    # 勾选协议
                    tos_agree = WebDriverWait(
                        ctx, 3, ignored_exceptions=ElementClickInterceptedException
                    ).until(EC.element_to_be_clickable((By.ID, "agree")))

                    # 点击接受
                    tos_submit = WebDriverWait(
                        ctx, 3, ignored_exceptions=ElementClickInterceptedException
                    ).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//span[text()='接受']/parent::button")
                        )
                    )
                    time.sleep(1)
                    tos_agree.click()
                    tos_submit.click()
                    return True
            # 窗口渲染出来后因不可抗力因素自然消解
            except (TimeoutException, StaleElementReferenceException):
                return

    @staticmethod
    def fall_in_captcha_runtime(ctx: ChallengerContext) -> Optional[bool]:
        """捕获隐藏在周免游戏订单中的人机挑战"""
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, ArmorUtils.HOOK_CHALLENGE))
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def surprise_warning_purchase(ctx: ChallengerContext) -> Optional[bool]:
        """
        处理弹窗遮挡消息。

        这是一个没有意义的操作，但无可奈何，需要更多的测试。
        :param ctx:
        :return:
        """

        try:
            surprise_obj = WebDriverWait(ctx, 2).until(
                EC.visibility_of_element_located((By.TAG_NAME, "h1"))
            )
            surprise_warning = surprise_obj.text
        except TimeoutException:
            return True

        if "成人内容" in surprise_warning:
            WebDriverWait(
                ctx, 2, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='继续']/parent::button")
                )
            ).click()
            return True
        if "内容品当前在您所在平台或地区不可用。" in surprise_warning:
            raise UnableToGet(surprise_warning)
        return False

    @staticmethod
    def payment_auto_submit(ctx: ChallengerContext) -> NoReturn:
        """认领游戏后订单自动提交 仅在常驻游戏中出现"""
        try:
            warning_text = (
                WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException)
                .until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@data-component='DownloadMessage']//span")
                    )
                )
                .text
            )
            if warning_text == "感谢您的购买":
                raise PaymentAutoSubmit(warning_text)
        except TimeoutException:
            pass

    @staticmethod
    def payment_blocked(ctx: ChallengerContext) -> NoReturn:
        """判断游戏锁区"""
        # 需要在 webPurchaseContainer 里执行
        try:
            warning_text = (
                WebDriverWait(ctx, 3, ignored_exceptions=WebDriverException)
                .until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//h2[@class='payment-blocked__msg']")
                    )
                )
                .text
            )
            if warning_text:
                raise PaymentBlockedWarning(warning_text)
        except TimeoutException:
            pass

    @staticmethod
    def timeout(loop_start: float, loop_timeout: float = 300) -> NoReturn:
        """任务超时锁"""
        if time.time() - loop_start > loop_timeout:
            raise AssertTimeout

    @staticmethod
    def purchase_status(
        ctx: ChallengerContext,
        page_link: str,
        get: bool,
        action_name: Optional[str] = "AssertUtils",
        init: Optional[bool] = True,
    ) -> Optional[str]:
        """
        断言当前上下文页面的游戏的在库状态。

        :param get:
        :param init:
        :param action_name:
        :param page_link:
        :param ctx:
        :return:
        """
        time.sleep(2)

        # 捕获按钮对象，根据按钮上浮动的提示信息断言游戏在库状态 超时的空对象主动抛出异常
        try:
            assert_obj = WebDriverWait(ctx, 30).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//span[@data-component='PurchaseCTA']//span[@data-component='Message']",
                    )
                )
            )
        except TimeoutException:
            return AssertUtils.ASSERT_OBJECT_EXCEPTION

        assert_info = assert_obj.text

        # 游戏名 超时的空对象主动抛出异常
        game_name = (
            WebDriverWait(ctx, 30, ignored_exceptions=ElementNotVisibleException)
            .until(EC.visibility_of_element_located((By.XPATH, "//h1")))
            .text
        )

        if game_name[-1] == "。":
            logger.warning(
                ToolBox.runtime_report(
                    motive="SKIP",
                    action_name=action_name,
                    message=f"🚫 {game_name}",
                    url=page_link,
                )
            )
            return AssertUtils.ASSERT_OBJECT_EXCEPTION

        if "已在" in assert_info:
            _message = "🛴 游戏已在库" if init else "🥂 领取成功"
            logger.info(
                ToolBox.runtime_report(
                    motive="GET",
                    action_name=action_name,
                    message=_message,
                    game=f"『{game_name}』",
                )
            )
            return AssertUtils.GAME_OK if init else AssertUtils.GAME_CLAIM

        if "获取" in assert_info:
            deadline: Optional[str] = None
            try:
                deadline = ctx.find_element(
                    By.XPATH,
                    "//div[@data-component='PDPSidebarLayout']"
                    "//span[contains(text(),'优惠截止')][@data-component='Message']",
                ).text
            except (NoSuchElementException, AttributeError):
                pass

            # 必须使用挑战者驱动领取周免游戏，处理潜在的人机验证
            if deadline:
                AssertUtils.wrong_driver(ctx, "♻ 请使用挑战者上下文领取周免游戏。")
                if get is True:
                    message = f"💰 正在为玩家领取周免游戏 {deadline}"
                else:
                    message = f"🛒 添加至购物车 {deadline}"
            else:
                if get is True:
                    message = "🚀 正在为玩家领取免费游戏"
                else:
                    message = "🛒 添加至购物车"
            if init:
                logger.success(
                    ToolBox.runtime_report(
                        motive="GET",
                        action_name=action_name,
                        message=message,
                        game=f"『{game_name}』",
                    )
                )

            return AssertUtils.GAME_PENDING

        if "购买" in assert_info:
            logger.warning(
                ToolBox.runtime_report(
                    motive="SKIP",
                    action_name=action_name,
                    message="🚧 这不是免费游戏",
                    game=f"『{game_name}』",
                )
            )
            return AssertUtils.GAME_NOT_FREE

        return AssertUtils.ASSERT_OBJECT_EXCEPTION

    @staticmethod
    def refund_info(ctx: ChallengerContext):
        """
        处理订单中的 退款及撤销权信息

        :param ctx:
        :return:
        """
        try:
            WebDriverWait(
                ctx, 2, ignored_exceptions=StaleElementReferenceException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='我同意']/ancestor::button")
                )
            ).click()
            logger.debug("[🍜] 处理 UK 地区账号的「退款及撤销权信息」。")
        except TimeoutException:
            pass

    @staticmethod
    def unreal_resource_load(ctx: ChallengerContext):
        """等待虚幻商店月供资源加载"""
        pending_locator = [
            "//i[text()='添加到购物车']",
            "//i[text()='购物车内']",
            "//span[text()='撰写评论']",
        ] * 10

        time.sleep(3)
        for locator in pending_locator:
            try:
                WebDriverWait(ctx, 1).until(
                    EC.element_to_be_clickable((By.XPATH, locator))
                )
                return True
            except TimeoutException:
                continue

    @staticmethod
    def unreal_surprise_license(ctx: ChallengerContext):
        try:
            WebDriverWait(ctx, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//span[text()='我已阅读并同意《最终用户许可协议》']")
                )
            ).click()
        except TimeoutException:
            pass
        else:
            WebDriverWait(ctx, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='接受']"))
            ).click()


class EpicAwesomeGamer:
    """白嫖人的基础设施"""

    # 操作对象参数
    URL_MASTER_HOST = "https://store.epicgames.com"
    URL_LOGIN_GAMES = "https://www.epicgames.com/id/login/epic?lang=zh-CN"
    URL_LOGIN_UNREAL = "https://www.unrealengine.com/id/login/epic?lang=zh-CN"
    URL_ACCOUNT_PERSONAL = "https://www.epicgames.com/account/personal"

    # 购物车结算成功
    URL_CART_SUCCESS = "https://store.epicgames.com/zh-CN/cart/success"

    URL_UNREAL_STORE = "https://www.unrealengine.com/marketplace/zh-CN/assets"
    URL_UNREAL_MONTH = (
        f"{URL_UNREAL_STORE}?count=20&sortBy=effectiveDate&sortDir=DESC&start=0&tag=4910"
    )

    AUTH_STR_GAMES = "games"
    AUTH_STR_UNREAL = "unreal"

    CLAIM_MODE_ADD = "add"
    CLAIM_MODE_GET = "get"
    ACTIVE_BINGO = "下单"

    def __init__(self):
        """定义了一系列领取免费游戏所涉及到的浏览器操作。"""
        # 实体对象参数
        self.action_name = "BaseAction"
        self.email, self.password = EPIC_EMAIL, EPIC_PASSWORD

        # 驱动参数
        self.loop_timeout = 300

        # 游戏获取结果的状态
        self.result = ""

        # 注册拦截机
        self._armor = ArmorUtils()
        self.assert_ = AssertUtils()

    # ======================================================
    # Reused Action Chains
    # ======================================================
    def _reset_page(
        self,
        ctx: ChallengerContext,
        page_link: str,
        ctx_cookies: List[dict],
        auth_str: str,
    ):
        if auth_str == self.AUTH_STR_GAMES:
            ctx.get(self.URL_ACCOUNT_PERSONAL)
        elif auth_str == self.AUTH_STR_UNREAL:
            ctx.get(self.URL_UNREAL_STORE)

        for cookie_dict in ctx_cookies:
            try:
                ctx.add_cookie(cookie_dict)
            except InvalidCookieDomainException as err:
                logger.error(
                    ToolBox.runtime_report(
                        motive="SKIP",
                        action_name=self.action_name,
                        error=err.msg,
                        domain=cookie_dict.get("domain", "null"),
                        name=cookie_dict.get("name", "null"),
                    )
                )

        ctx.get(page_link)

    @staticmethod
    def _move_product_to_wishlist(ctx: ChallengerContext):
        try:
            move_buttons = ctx.find_elements(By.XPATH, "//span[text()='移至愿望清单']")
        except NoSuchElementException:
            pass
        else:
            for button in move_buttons:
                try:
                    button.click()
                except WebDriverException:
                    continue

    @staticmethod
    def _switch_to_payment_iframe(ctx):
        payment_frame = WebDriverWait(
            ctx, 5, ignored_exceptions=ElementNotVisibleException
        ).until(EC.presence_of_element_located((By.XPATH, ArmorUtils.HOOK_PURCHASE)))
        ctx.switch_to.frame(payment_frame)

    @staticmethod
    def _accept_agreement(ctx):
        try:
            WebDriverWait(
                ctx, 2, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class,'payment-check-box')]")
                )
            ).click()
        except TimeoutException:
            pass

    @staticmethod
    def _click_order_button(ctx, timeout: int = 20) -> Optional[bool]:
        try:
            time.sleep(0.5)
            WebDriverWait(
                ctx, timeout, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(@class,'payment-btn')]")
                )
            ).click()
            return True
        # 订单界面未能按照预期效果出现，在超时范围内重试若干次。
        except TimeoutException:
            ctx.switch_to.default_content()
            return False

    def _duel_with_challenge(self, ctx) -> Optional[bool]:
        """
        动态处理人机挑战
        :param ctx:
        :return: True挑战成功，False挑战失败/需要跳过，None其他信号
        """
        if self._armor.fall_in_captcha_runtime(ctx):
            self.assert_.wrong_driver(ctx, "任务中断，请使用挑战者上下文处理意外弹出的人机验证。")
            try:
                return self._armor.anti_hcaptcha(ctx, door="free")
            except (ChallengeReset, WebDriverException):
                pass

    # ======================================================
    # Business Action Chains
    # ======================================================

    def _activate_payment(self, api: ChallengerContext, mode="get") -> Optional[bool]:
        """激活游戏订单"""
        element_xpath = {
            self.CLAIM_MODE_GET: "//button[@data-testid='purchase-cta-button']",
            self.CLAIM_MODE_ADD: "//button[@data-testid='add-to-cart-cta-button']",
            self.ACTIVE_BINGO: "//span[text()='下单']/parent::button",
        }
        for _ in range(5):
            try:
                WebDriverWait(
                    api, 5, ignored_exceptions=ElementClickInterceptedException
                ).until(
                    EC.element_to_be_clickable((By.XPATH, element_xpath[mode]))
                ).click()
                return True
            # 加载超时，继续测试
            except TimeoutException:
                continue
            # 出现弹窗遮挡
            except ElementClickInterceptedException:
                try:
                    if self.assert_.surprise_warning_purchase(api) is True:
                        continue
                except UnableToGet:
                    return False

    def _handle_payment(self, ctx: ChallengerContext) -> None:
        """
        处理游戏订单

        逻辑过于复杂，需要重构。此处为了一套代码涵盖各种情况，做了很多妥协。
        需要针对 周免游戏的订单处理 设计一套执行效率更高的业务模型。
        :param ctx:
        :return:
        """
        # [🍜] Switch to the [Purchase Container] iframe.
        try:
            self._switch_to_payment_iframe(ctx)
        except TimeoutException:
            try:
                warning_layout = ctx.find_element(
                    By.XPATH, "//div[@data-component='WarningLayout']"
                )
                warning_text = warning_layout.text
                # Handle delayed loading of cookies.
                if "依旧要购买吗" in warning_text:
                    return
                # Handle Linux User-Agent Heterogeneous Services.
                if "设备不受支持" in warning_text:
                    ctx.find_element(
                        By.XPATH, "//span[text()='继续']/parent::button"
                    ).click()
                    return self._handle_payment(ctx)
            except NoSuchElementException:
                pass

        # [🍜] 判断游戏锁区
        self.assert_.payment_blocked(ctx)

        # [🍜] Ignore: Click the [Accept Agreement] confirmation box.
        self._accept_agreement(ctx)

        # [🍜] Click the [order] button.
        response = self._click_order_button(ctx)
        if not response:
            return

        # [🍜] 处理 UK 地区账号的「退款及撤销权信息」。
        self.assert_.refund_info(ctx)

        # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
        self._duel_with_challenge(ctx)

        # [🍜] Switch to default iframe.
        ctx.switch_to.default_content()
        ctx.refresh()

    def login(self, email: str, password: str, ctx: ChallengerContext, auth_str: str):
        """
        作为被动方式，登陆账号，刷新 identity token。

        此函数不应被主动调用，应当作为 refresh identity token / Challenge 的辅助函数。
        :param auth_str:
        :param ctx:
        :param email:
        :param password:
        :return:
        """
        if auth_str == self.AUTH_STR_GAMES:
            ctx.get(self.URL_LOGIN_GAMES)
        elif auth_str == self.AUTH_STR_UNREAL:
            ctx.get(self.URL_LOGIN_UNREAL)

        WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.ID, "email"))
        ).send_keys(email)

        WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.ID, "password"))
        ).send_keys(password)

        WebDriverWait(ctx, 60, ignored_exceptions=ElementClickInterceptedException).until(
            EC.element_to_be_clickable((By.ID, "sign-in"))
        ).click()

        logger.debug(
            ToolBox.runtime_report(
                motive="MATCH", action_name=self.action_name, message="实体信息注入完毕"
            )
        )

    def cart_success(self, ctx: ChallengerContext):
        """
        提高跳过人机挑战的期望，使用轮询的方式检测运行状态
        确保进入此函数时，已经点击 order 按钮，并已处理欧盟和新手协议，无任何遮挡。
        :param ctx:
        :return:
        """

        def annealing():
            logger.debug(f"[🎃] 退火成功 - {ctx.current_url=}")
            return True

        _fall_in_challenge = 0
        for _ in range(30):
            ctx.switch_to.default_content()
            try:
                payment_iframe = WebDriverWait(ctx, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, ArmorUtils.HOOK_PURCHASE))
                )
            # 订单消失
            except TimeoutException:
                return annealing()
            else:
                try:
                    WebDriverWait(ctx, 0.5).until(EC.url_to_be(self.URL_CART_SUCCESS))
                    return annealing()
                except TimeoutException:
                    pass
                # 还原现场
                try:
                    ctx.switch_to.frame(payment_iframe)
                except WebDriverException:
                    return annealing()
                if _fall_in_challenge > 2:
                    return False
                # 进入必然存在的人机挑战框架
                try:
                    challenge_iframe = ctx.find_element(
                        By.XPATH, ArmorUtils.HOOK_CHALLENGE
                    )
                except NoSuchElementException:
                    continue
                else:
                    ctx.switch_to.frame(challenge_iframe)
                    try:
                        ctx.find_element(By.XPATH, "//div[@class='prompt-text']")
                    except NoSuchElementException:
                        continue
                    else:
                        _fall_in_challenge += 1

    def cart_handle_payment(self, ctx: ChallengerContext):
        # [🍜] Switch to the [Purchase Container] iframe.
        try:
            self._switch_to_payment_iframe(ctx)
            logger.debug("[🌀] 切换至内联订单框架")
        except TimeoutException:
            ctx.switch_to.default_content()
            return

        # [🍜] Click the [order] button.
        logger.debug("[⚔] 激活人机挑战...")
        response = self._click_order_button(ctx, 12)
        if not response:
            return

        # [🍜] 处理 UK 地区账号的「退款及撤销权信息」。
        self.assert_.refund_info(ctx)

        # [🍜] 提高跳过人机挑战的期望，使用轮询的方式检测运行状态
        if not self.cart_success(ctx):
            # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
            logger.debug("[⚔] 捕获隐藏在订单中的人机挑战...")
            self._duel_with_challenge(ctx)

        # [🍜] Switch to default iframe.
        logger.debug("[🌀] 弹出内联订单框架...")
        ctx.switch_to.default_content()
        ctx.refresh()

        return True

    def unreal_activate_payment(self, ctx: ChallengerContext, init=True):
        """从虚幻商店购物车激活订单"""
        # =======================================================
        # [🍜] 将月供内容添加到购物车
        # =======================================================
        try:
            offer_objs = ctx.find_elements(By.XPATH, "//i[text()='添加到购物车']")
            if len(offer_objs) == 0:
                raise NoSuchElementException
        # 不存在可添加内容
        except NoSuchElementException:
            # 商品在购物车
            try:
                hook_objs = ctx.find_elements(By.XPATH, "//i[text()='购物车内']")
                if len(hook_objs) == 0:
                    raise NoSuchElementException
                logger.debug(
                    ToolBox.runtime_report(
                        motive="PENDING", action_name=self.action_name, message="正在清空购物车"
                    )
                )
            # 购物车为空
            except NoSuchElementException:
                # 月供内容均已在库
                try:
                    ctx.find_element(By.XPATH, "//span[text()='撰写评论']")
                    _message = "本月免费内容均已在库" if init else "🥂 领取成功"
                    logger.success(
                        ToolBox.runtime_report(
                            motive="GET", action_name=self.action_name, message=_message
                        )
                    )
                    return AssertUtils.GAME_OK if init else AssertUtils.GAME_CLAIM
                # 异常情况：需要处理特殊情况，递归可能会导致无意义的死循环
                except NoSuchElementException:
                    return self.unreal_activate_payment(ctx, init=init)
        # 存在可添加的月供内容
        else:
            # 商品名
            offer_names = ctx.find_elements(By.XPATH, "//article//h3//a")
            # 商品状态：添加到购入车/购物车内/撰写评论(已在库)
            offer_buttons = ctx.find_elements(
                By.XPATH, "//div[@class='asset-list-group']//article//i"
            )
            offer_labels = [offer_button.text for offer_button in offer_buttons]
            # 逐级遍历将可添加的月供内容移入购物车
            for i, offer_label in enumerate(offer_labels):
                if offer_label == "添加到购物车":
                    offer_name = "null"
                    try:
                        offer_name = offer_names[i].text
                    except (IndexError, AttributeError):
                        pass
                    logger.debug(
                        ToolBox.runtime_report(
                            motive="PENDING",
                            action_name=self.action_name,
                            message="添加到购物车",
                            hook=f"『{offer_name}』",
                        )
                    )
                    offer_buttons[i].click()
                    time.sleep(1)
            time.sleep(1.5)

        # [🍜] 激活购物车
        try:
            ctx.find_element(By.XPATH, "//div[@class='shopping-cart']").click()
            logger.debug(
                ToolBox.runtime_report(
                    motive="HANDLE", action_name=self.action_name, message="激活购物车"
                )
            )
        except NoSuchElementException:
            ctx.refresh()
            time.sleep(2)
            return self.unreal_activate_payment(ctx)

        # [🍜] 激活订单
        try:
            WebDriverWait(ctx, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='去支付']"))
            ).click()
            logger.debug(
                ToolBox.runtime_report(
                    motive="HANDLE", action_name=self.action_name, message="激活订单"
                )
            )
        except TimeoutException:
            ctx.refresh()
            time.sleep(2)
            return self.unreal_activate_payment(ctx, init=init)

        # [🍜] 处理首次下单的许可协议
        self.assert_.unreal_surprise_license(ctx)

        return AssertUtils.GAME_PENDING

    def unreal_handle_payment(self, ctx: ChallengerContext):
        # [🍜] Switch to the [Purchase Container] iframe.
        try:
            self._switch_to_payment_iframe(ctx)
        except TimeoutException:
            pass

        # [🍜] Click the [order] button.
        response = self._click_order_button(ctx)
        if not response:
            return

        # [🍜] 处理 UK 地区账号的「退款及撤销权信息」。
        self.assert_.refund_info(ctx)

        # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
        self._duel_with_challenge(ctx)

        # [🍜] Switch to default iframe.
        ctx.switch_to.default_content()
        ctx.refresh()


class CookieManager(EpicAwesomeGamer):
    """管理上下文身份令牌"""

    def __init__(self, auth_str):
        super().__init__()

        self.action_name = "CookieManager"
        self.auth_str = auth_str
        self.path_ctx_cookies = os.path.join(DIR_COOKIES, "ctx_cookies.yaml")
        self.ctx_session = None

    def _t(self) -> str:
        return (
            sha256(f"{self.email[-3::-1]}{self.auth_str}".encode("utf-8")).hexdigest()
            if self.email
            else ""
        )

    def load_ctx_cookies(self) -> Optional[List[dict]]:
        """载入本地缓存的身份令牌"""
        if not os.path.exists(self.path_ctx_cookies):
            return []

        with open(self.path_ctx_cookies, "r", encoding="utf8") as file:
            data: dict = yaml.safe_load(file)

        ctx_cookies = data.get(self._t(), []) if isinstance(data, dict) else []
        if not ctx_cookies:
            return []

        logger.debug(
            ToolBox.runtime_report(
                motive="LOAD",
                action_name=self.action_name,
                message="Load context cookie.",
            )
        )

        return ctx_cookies

    def save_ctx_cookies(self, ctx_cookies: List[dict]) -> None:
        """在本地缓存身份令牌"""
        _data = {}

        if os.path.exists(self.path_ctx_cookies):
            with open(self.path_ctx_cookies, "r", encoding="utf8") as file:
                stream: dict = yaml.safe_load(file)
                _data = _data if not isinstance(stream, dict) else stream

        _data.update({self._t(): ctx_cookies})

        with open(self.path_ctx_cookies, "w", encoding="utf8") as file:
            yaml.dump(_data, file)

        logger.debug(
            ToolBox.runtime_report(
                motive="SAVE",
                action_name=self.action_name,
                message="Update Context Cookie.",
            )
        )

    def is_available_cookie(self, ctx_cookies: Optional[List[dict]] = None) -> bool:
        """检测 Cookie 是否有效"""
        ctx_cookies = self.load_ctx_cookies() if ctx_cookies is None else ctx_cookies
        if not ctx_cookies:
            return False

        headers = {"cookie": ToolBox.transfer_cookies(ctx_cookies)}

        scraper = cloudscraper.create_scraper()
        response = scraper.get(
            self.URL_ACCOUNT_PERSONAL, headers=headers, allow_redirects=False
        )

        if response.status_code == 200:
            return True
        return False

    def refresh_ctx_cookies(
        self, silence: bool = True, ctx_session=None, keep_live=None
    ) -> Optional[bool]:
        """
        更新上下文身份信息，若认证数据过期则弹出 login 任务更新令牌。
        :param keep_live: keep actively to the challenger context
        :param ctx_session:
        :param silence:
        :return:
        """
        # {{< Check Context Cookie Validity >}}
        if self.is_available_cookie():
            logger.success(
                ToolBox.runtime_report(
                    motive="CHECK",
                    action_name=self.action_name,
                    message="The identity token is valid.",
                )
            )
            return True
        # {{< Done >}}

        # {{< Insert Challenger Context >}}
        ctx = get_challenge_ctx(silence=silence) if ctx_session is None else ctx_session
        logger.success(
            ToolBox.runtime_report(
                motive="MATCH",
                action_name="__Context__",
                message="🎮 启动挑战者上下文",
                ctx_session=bool(ctx_session),
            )
        )

        try:
            balance_operator = -1
            while balance_operator < 8:
                balance_operator += 1

                # Enter the account information and jump to the man-machine challenge page.
                self.login(self.email, self.password, ctx=ctx, auth_str=self.auth_str)

                # Assert if you are caught in a man-machine challenge.
                try:
                    fallen = self._armor.fall_in_captcha_login(ctx=ctx)
                except AssertTimeout:
                    balance_operator += 1
                    continue
                else:
                    # Approved.
                    if fallen == self._armor.AUTH_SUCCESS:
                        break
                    # Winter is coming, so hear me roar!
                    if fallen == self._armor.AUTH_CHALLENGE:
                        if self._armor.anti_hcaptcha(ctx, door="login"):
                            break
                        balance_operator += 0.5
                        continue
            else:
                logger.critical(
                    ToolBox.runtime_report(
                        motive="MISS",
                        action_name=self.action_name,
                        message="Identity token update failed.",
                    )
                )
                return False
        except ChallengeReset:
            pass
        except AuthException as err:
            raise err
        except ChallengeTimeout as error:
            logger.critical(
                ToolBox.runtime_report(
                    motive="SKIP", action_name=self.action_name, message=error.msg
                )
            )
            return False
        else:
            # Store contextual authentication information.
            if self.auth_str != "games":
                ctx.get(self.URL_LOGIN_UNREAL)
            self.save_ctx_cookies(ctx_cookies=ctx.get_cookies())
            return self.is_available_cookie(ctx_cookies=ctx.get_cookies())
        finally:
            if ctx_session is None:
                if not keep_live:
                    ctx.quit()
                else:
                    self.ctx_session = ctx
        # {{< Done >}}

        return True
