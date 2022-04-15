# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import asyncio
import json.decoder
import os
import sys
import time
import urllib.request
from typing import List, Optional, NoReturn, Dict, Union

import cloudscraper
from lxml import etree
from requests.exceptions import RequestException
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
from undetected_chromedriver import Chrome

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
    AshFramework,
    ChallengeReset,
)
from .exceptions import (
    AssertTimeout,
    UnableToGet,
    CookieExpired,
    SwitchContext,
    PaymentException,
    AuthException,
    PaymentAutoSubmit,
)

# 显示人机挑战的DEBUG日志
ARMOR_DEBUG = True


class ArmorUtils(ArmorCaptcha):
    """人机对抗模组"""

    def __init__(self, debug: bool = ARMOR_DEBUG):
        super().__init__(dir_workspace=DIR_CHALLENGE, debug=debug)

        # 重定向工作空间
        self.model = YOLO(DIR_MODEL)

    @staticmethod
    def fall_in_captcha_login(ctx: Chrome) -> Optional[bool]:
        """
        判断在登录时是否遇到人机挑战

        :param ctx:
        :return: True：已进入人机验证页面，False：跳转到个人主页
        """

        def _ajax_cookie_check_need_login(beat_dance: int = 0) -> Optional[bool]:
            """
            检验 AJAX COOKIE 是否有效
            :return: True无效 | False有效
            """
            # 防止过失操作
            time.sleep(0.3 + beat_dance)

            _api = "https://www.epicgames.com/account/v2/ajaxCheckLogin"
            scraper = cloudscraper.create_scraper()
            try:
                response = scraper.get(
                    _api,
                    headers={"cookie": ToolBox.transfer_cookies(ctx.get_cookies())},
                    timeout=2,
                )
                return response.json()["needLogin"]
            except (json.decoder.JSONDecodeError, KeyError):
                return True
            # Timeout/ConnectionError
            except RequestException:
                return True
            except Exception as err:  # noqa
                logger.warning(err)
                return None

        threshold_timeout = 69
        start = time.time()
        flag_ = ctx.current_url
        retry_times = -1

        while True:
            retry_times += 1

            # 判断上下文身份令牌是否已生效
            if ctx.current_url != flag_ or not _ajax_cookie_check_need_login(
                beat_dance=retry_times
            ):
                return False

            # 任务超时中断循环
            if time.time() - start > threshold_timeout:
                raise AssertTimeout("任务超时：判断是否陷入人机验证")

            # 启发式搜索::令牌暂未生效，任务仍未超时，检测隐藏在登录界面的人机挑战。
            try:
                ctx.switch_to.frame(
                    ctx.find_element(By.XPATH, "//iframe[contains(@title,'content')]")
                )
                ctx.find_element(By.XPATH, "//div[@class='prompt-text']")
                return True
            except WebDriverException:
                pass
            finally:
                ctx.switch_to.default_content()

    @staticmethod
    def fall_in_captcha_runtime(ctx: Chrome) -> Optional[bool]:
        """
        判断在下单时是否遇到人机挑战

        # "//div[@id='talon_frame_checkout_free_prod']"
        :param ctx:
        :return:
        """
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//iframe[contains(@title,'content')]")
                )
            )
            return True
        except TimeoutException:
            return False

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
        if "win" in sys.platform:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(ImageDownloader(docker=docker_).subvert(workers="fast"))
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                ImageDownloader(docker=docker_).subvert(workers="fast")
            )

        self.runtime_workspace = workspace_

    def challenge_success(
        self, ctx: Chrome, init: bool = True, **kwargs
    ) -> Optional[bool]:
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

        def _continue_action():
            try:
                time.sleep(3)
                ctx.find_element(By.XPATH, "//div[@class='task-image']")
            except NoSuchElementException:
                return True
            else:
                return False

        def _high_threat_proxy_access():
            """error-text:: 请再试一次"""
            # 未设置子网桥系统代理
            if not urllib.request.getproxies():
                return False

            try:
                WebDriverWait(ctx, 2, ignored_exceptions=WebDriverException).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "//div[@class='error-text']")
                    )
                )
                return True
            except TimeoutException:
                return False

        door: str = kwargs.get("door", "login")

        flag = ctx.current_url

        # 首轮测试后判断短时间内页内是否存在可点击的拼图元素
        # hcaptcha 最多两轮验证，一般情况下，账号信息有误仅会执行一轮，然后返回登录窗格提示密码错误
        # 其次是被识别为自动化控制，这种情况也是仅执行一轮，回到登录窗格提示“返回数据错误”
        if init and not _continue_action():
            self.log("挑战继续")
            return False

        if not init and _high_threat_proxy_access():
            self.log("挑战被迫重置 可能使用了高威胁的代理IP")

        try:
            challenge_reset = WebDriverWait(
                ctx, 5, ignored_exceptions=WebDriverException
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@class='MuiAlert-message']")
                )
            )
        except TimeoutException:
            # 如果挑战通过，自动跳转至其他页面（也即离开当前网址）
            try:
                WebDriverWait(ctx, 10).until(EC.url_changes(flag))
            # 如果挑战未通过，可能为“账号信息错误”“分数太低”“自动化特征被识别”
            except TimeoutException:
                if door == "login":
                    self.log("断言超时，挑战继续")
                return False
            # 人机挑战通过，但可能还需处理 `2FA` 问题（超纲了）
            else:
                # 如果没有遇到双重认证，人机挑战成功
                if "id/login/mfa" not in ctx.current_url:
                    self.log("挑战成功")
                    return True
                raise AuthException("人机挑战已退出 error=遭遇意外的 2FA 双重认证")
        else:
            self.log("挑战失败，需要重置挑战")
            challenge_reset.click()
            raise ChallengeReset

    def anti_hcaptcha(self, ctx: Chrome, door: str = "login") -> Optional[bool]:  # noqa
        """
        Handle hcaptcha challenge

        ## Reference

        M. I. Hossen and X. Hei, "A Low-Cost Attack against the hCaptcha System," 2021 IEEE Security
        and Privacy Workshops (SPW), 2021, pp. 422-431, doi: 10.1109/SPW53761.2021.00061.

        > ps:该篇文章中的部分内容已过时，现在 hcaptcha challenge 远没有作者说的那么容易应付。

        :param door: [login free]
        :param ctx:
        :return:
        """
        # [👻] 进入人机挑战关卡
        ctx.switch_to.frame(
            WebDriverWait(ctx, 5, ignored_exceptions=ElementNotVisibleException).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//iframe[contains(@title,'content')]")
                )
            )
        )

        # [👻] 获取挑战图片
        # 多轮验证标签不会改变
        self.get_label(ctx)
        if self.tactical_retreat():
            ctx.switch_to.default_content()
            return False

        # [👻] 注册解决方案
        # 根据挑战类型自动匹配不同的模型
        model = self.switch_solution(mirror=self.model)

        # [👻] 人机挑战！
        try:
            for index in range(2):
                self.mark_samples(ctx)

                self.download_images()

                self.challenge(ctx, model=model)

                result = self.challenge_success(ctx, init=not bool(index), door=door)

                # 仅一轮测试就通过
                if index == 0 and result:
                    break
                # 断言超时
                if index == 1 and result is False:
                    raise TimeoutException
        # 提交结果断言超时或 mark_samples() 等待超时
        except TimeoutException:
            ctx.switch_to.default_content()
            return False
        # 捕获重置挑战的请求信号
        except ChallengeReset:
            ctx.switch_to.default_content()
            return self.anti_hcaptcha(ctx, door=door)
        # 回到主线剧情
        else:
            ctx.switch_to.default_content()
            return True


class AssertUtils:
    """处理穿插在认领过程中意外出现的遮挡信息"""

    # 特征指令/简易错误
    # 此部分状态作为消息模板的一部分，尽量简短易理解
    COOKIE_EXPIRED = "💥 饼干过期了"
    ASSERT_OBJECT_EXCEPTION = "🚫 无效的断言对象"
    GAME_OK = "🛴 已在库"
    GAME_PENDING = "👀 待认领"
    GAME_CLAIM = "💰 领取成功"
    GAME_NOT_FREE = "🦽 付费游戏"

    @staticmethod
    def login_error(ctx: Chrome) -> bool:
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
    def surprise_license(ctx: Chrome) -> Optional[bool]:
        """
        新用户首次购买游戏需要处理许可协议书

        :param ctx:
        :return:
        """
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
    def fall_in_captcha_runtime(ctx: Chrome) -> Optional[bool]:
        """捕获隐藏在周免游戏订单中的人机挑战"""
        try:
            # //iframe[@id='talon_frame_checkout_free_prod']
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//iframe[contains(@title,'content')]")
                )
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def surprise_warning_purchase(ctx: Chrome) -> Optional[bool]:
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
    def payment_auto_submit(ctx: Chrome) -> NoReturn:
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
                raise PaymentAutoSubmit
        except TimeoutException:
            pass

    @staticmethod
    def payment_blocked(ctx: Chrome) -> NoReturn:
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
                raise PaymentException(warning_text)
        except TimeoutException:
            pass

    @staticmethod
    def timeout(loop_start: float, loop_timeout: float = 300) -> NoReturn:
        """任务超时锁"""
        if time.time() - loop_start > loop_timeout:
            raise AssertTimeout

    @staticmethod
    def purchase_status(
        ctx: Chrome,
        page_link: str,
        action_name: Optional[str] = "AssertUtils",
        init: Optional[bool] = True,
    ) -> Optional[str]:
        """
        断言当前上下文页面的游戏的在库状态。

        :param init:
        :param action_name:
        :param page_link:
        :param ctx:
        :return:
        """
        time.sleep(2)

        # 捕获按钮对象，根据按钮上浮动的提示信息断言游戏在库状态 超时的空对象主动抛出异常
        try:
            assert_obj = WebDriverWait(ctx, 30, WebDriverException).until(
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
                AssertUtils.wrong_driver(ctx, "♻ 使用挑战者上下文领取周免游戏。")

            message = "🚀 发现免费游戏" if not deadline else f"💰 发现周免游戏 {deadline}"
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
    def refund_info(ctx: Chrome):
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
        except TimeoutException:
            pass

    @staticmethod
    def unreal_resource_load(ctx: Chrome):
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
    def unreal_surprise_license(ctx: Chrome):
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


class AwesomeFreeMan:
    """白嫖人的基础设施"""

    # 操作对象参数
    URL_MASTER_HOST = "https://store.epicgames.com"
    URL_LOGIN_GAMES = "https://www.epicgames.com/id/login/epic?lang=zh-CN"
    URL_LOGIN_UNREAL = "https://www.unrealengine.com/id/login/epic?lang=zh-CN"
    URL_ACCOUNT_PERSONAL = "https://www.epicgames.com/account/personal"

    URL_UNREAL_STORE = "https://www.unrealengine.com/marketplace/zh-CN/assets"
    URL_UNREAL_MONTH = (
        f"{URL_UNREAL_STORE}?count=20&sortBy=effectiveDate&sortDir=DESC&start=0&tag=4910"
    )

    def __init__(self):
        """定义了一系列领取免费游戏所涉及到的浏览器操作。"""

        # 实体对象参数
        self.action_name = "BaseAction"
        self.email, self.password = EPIC_EMAIL, EPIC_PASSWORD

        # 驱动参数
        self.path_ctx_cookies = os.path.join(DIR_COOKIES, "ctx_cookies.yaml")
        self.loop_timeout = 300

        # 游戏获取结果的状态
        self.result = ""

        # 注册拦截机
        self._armor = ArmorUtils()
        self.assert_ = AssertUtils()

    def _reset_page(self, ctx: Chrome, page_link: str, ctx_cookies, _auth_str="games"):
        if _auth_str == "games":
            ctx.get(self.URL_ACCOUNT_PERSONAL)
        elif _auth_str == "unreal":
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

    def _login(self, email: str, password: str, ctx: Chrome, _auth_str="games") -> None:
        """
        作为被动方式，登陆账号，刷新 identity token。

        此函数不应被主动调用，应当作为 refresh identity token / Challenge 的辅助函数。
        :param ctx:
        :param email:
        :param password:
        :return:
        """
        if _auth_str == "games":
            ctx.get(self.URL_LOGIN_GAMES)
        elif _auth_str == "unreal":
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

    def _activate_payment(self, api: Chrome) -> Optional[bool]:
        """
        激活游戏订单

        :param api:
        :return:
        """
        for _ in range(5):
            try:
                WebDriverWait(
                    api, 5, ignored_exceptions=ElementClickInterceptedException
                ).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@data-testid='purchase-cta-button']")
                    )
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

    def _handle_payment(self, ctx: Chrome) -> None:
        """
        处理游戏订单

        逻辑过于复杂，需要重构。此处为了一套代码涵盖各种情况，做了很多妥协。
        需要针对 周免游戏的订单处理 设计一套执行效率更高的业务模型。
        :param ctx:
        :return:
        """

        # [🍜] Switch to the [Purchase Container] iframe.
        try:
            payment_frame = WebDriverWait(
                ctx, 5, ignored_exceptions=ElementNotVisibleException
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='webPurchaseContainer']//iframe")
                )
            )
            ctx.switch_to.frame(payment_frame)
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

        # [🍜] Click the [order] button.
        try:
            time.sleep(0.5)
            WebDriverWait(
                ctx, 20, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(@class,'payment-btn')]")
                )
            ).click()
        # 订单界面未能按照预期效果出现，在超时范围内重试若干次。
        except TimeoutException:
            ctx.switch_to.default_content()
            return

        # [🍜] 处理 UK 地区账号的「退款及撤销权信息」。
        self.assert_.refund_info(ctx)

        # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
        if self._armor.fall_in_captcha_runtime(ctx):
            self.assert_.wrong_driver(ctx, "任务中断，请使用挑战者上下文处理意外弹出的人机验证。")
            try:
                self._armor.anti_hcaptcha(ctx, door="free")
            except (ChallengeReset, WebDriverException):
                pass

        # [🍜] Switch to default iframe.
        ctx.switch_to.default_content()
        ctx.refresh()

    def _get_free_game(
        self, page_link: str, api_cookies: List[dict], ctx: Chrome
    ) -> Optional[str]:
        """
        获取免费游戏

        需要加载cookie后使用，避免不必要的麻烦。
        :param page_link:
        :param api_cookies:
        :param ctx:
        :return:
        """
        if not api_cookies:
            raise CookieExpired(self.assert_.COOKIE_EXPIRED)

        _loop_start = time.time()
        init = True
        while True:
            # [🚀] 重载身份令牌
            # InvalidCookieDomainException：需要 2 次 GET 重载 cookie relative domain
            # InvalidCookieDomainException：跨域认证，访问主域名或过滤异站域名信息
            self._reset_page(ctx=ctx, page_link=page_link, ctx_cookies=api_cookies)

            # [🚀] 断言游戏的在库状态
            self.assert_.surprise_warning_purchase(ctx)
            self.result = self.assert_.purchase_status(
                ctx, page_link, self.action_name, init
            )
            # 当游戏不处于<待认领>状态时跳过后续业务
            if self.result != self.assert_.GAME_PENDING:
                # <游戏状态断言超时>或<检测到异常的实体对象>
                # 在超时阈值内尝试重新拉起服务
                if self.result == self.assert_.ASSERT_OBJECT_EXCEPTION:
                    continue
                # 否则游戏状态处于<领取成功>或<已在库>或<付费游戏>
                break

            # [🚀] 激活游戏订单
            # Maximum sleep time -> 12s
            self._activate_payment(ctx)

            # [🚀] 新用户首次购买游戏需要处理许可协议书
            # Maximum sleep time -> 3s
            if self.assert_.surprise_license(ctx):
                ctx.refresh()
                continue

            # [🚀] 订单消失
            # Maximum sleep time -> 5s
            self.assert_.payment_auto_submit(ctx)

            # [🚀] 处理游戏订单
            self._handle_payment(ctx)

            # [🚀] 更新上下文状态
            init = False
            self.assert_.timeout(_loop_start, self.loop_timeout)

        return self.result

    def _get_free_dlc_details(
        self, ctx_url: str, ctx_cookies: List[dict]
    ) -> Optional[List[Dict[str, Union[str, bool]]]]:
        """
        1. 检测一个游戏实体是否存在免费附加内容
        2. 将可领取的免费附加内容编织成任务对象并返回
        3. 一个游戏实体可能存在多个可领取的免费DLC
        :param ctx_url: 游戏本体商城链接
        :param ctx_cookies:
        :return: [{"url": url of dlc, "name": name of dlc, "dlc": True}, ... ]
        """

        def handle_html(url_):
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36",
                "cookie": ToolBox.transfer_cookies(ctx_cookies),
            }
            scraper = cloudscraper.create_scraper()
            response_ = scraper.get(url_, headers=headers, allow_redirects=False)
            tree_ = etree.HTML(response_.content)

            return tree_, response_

        # [🚀] 检测当前商品是否有附加内容
        tree, response = handle_html(ctx_url)
        dlc_tag = tree.xpath(
            "//li[@data-component='PDPTertiaryNavigation']//a[contains(@href,'dlc')]"
        )
        if not dlc_tag:
            return

        # [🚀] 检测当前商品是否有免费的DLC
        dlc_page = (
            f"{self.URL_MASTER_HOST}{dlc_tag[0].attrib.get('href')}?"
            f"sortBy=relevancy&sortDir=DESC&priceTier=tierFree&count=40&start=0"
        )
        dlc_tree, response = handle_html(dlc_page)
        if dlc_tree.xpath("//span[text()='未找到结果']"):
            return

        # [🚀] 返回当前商品所有免费DLC链接
        dlc_tags: list = dlc_tree.xpath("//div[@data-component='DiscoverCard']//a")
        dlc_details = {}
        for tag in dlc_tags:
            # [📝] 获取 DLC 名称
            aria_label = tag.attrib.get("aria-label")
            try:
                name = aria_label.split(",")[0]
            except (IndexError, AttributeError):
                name = response.url.split("/")[-1]

            # 部分地区账号会被重定向至附加内容的默认页面
            # 此页面未触发筛选器，混杂着付费/免费的附加内容
            is_free = True
            try:
                # 重新判断当前游戏的状态，清洗付费游戏
                if "tierFree" not in response.url or response.status_code == 302:
                    is_free = aria_label.split(",")[-1].strip() == "0"
            # 当出现意外的标签时将此实例视为免费游戏送入任务队列
            # 下层驱动中有更加明确的游戏状态用以剔除杂质
            except (IndexError, AttributeError):
                pass

            # 编织缓存
            if is_free:
                url = f"{self.URL_MASTER_HOST}{tag.attrib.get('href')}"
                dlc_detail = {"url": url, "name": name, "dlc": True}
                dlc_details.update({url: dlc_detail})

        return list(dlc_details.values())

    def _get_free_resource(self, page_link: str, ctx_cookies: List[dict], ctx: Chrome):
        return self._get_free_game(page_link=page_link, api_cookies=ctx_cookies, ctx=ctx)

    def _unreal_activate_payment(
        self, ctx: Chrome, action_name="UnrealClaimer", init=True
    ):
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
                        motive="PENDING", action_name=action_name, message="正在清空购物车"
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
                            motive="GET", action_name=action_name, message=_message
                        )
                    )
                    return AssertUtils.GAME_OK if init else AssertUtils.GAME_CLAIM
                # 异常情况：需要处理特殊情况，递归可能会导致无意义的死循环
                except NoSuchElementException:
                    return self._unreal_activate_payment(ctx, action_name, init=init)
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
                            action_name=action_name,
                            message="添加到购物车",
                            hook=f"『{offer_name}』",
                        )
                    )
                    offer_buttons[i].click()

        # [🍜] 激活购物车
        try:
            ctx.find_element(By.XPATH, "//div[@class='shopping-cart']").click()
            logger.debug(
                ToolBox.runtime_report(
                    motive="HANDLE", action_name=action_name, message="激活购物车"
                )
            )
        except NoSuchElementException:
            ctx.refresh()
            time.sleep(2)
            return self._activate_payment(ctx)

        # [🍜] 激活订单
        try:
            WebDriverWait(ctx, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='去支付']"))
            ).click()
            logger.debug(
                ToolBox.runtime_report(
                    motive="HANDLE", action_name=action_name, message="激活订单"
                )
            )
        except TimeoutException:
            ctx.refresh()
            time.sleep(2)
            return self._unreal_activate_payment(ctx, action_name, init=init)

        # [🍜] 处理首次下单的许可协议
        self.assert_.unreal_surprise_license(ctx)

        return AssertUtils.GAME_PENDING

    def _unreal_handle_payment(self, ctx: Chrome):
        # [🍜] Switch to the [Purchase Container] iframe.
        try:
            payment_frame = WebDriverWait(
                ctx, 5, ignored_exceptions=ElementNotVisibleException
            ).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='webPurchaseContainer']//iframe")
                )
            )
            ctx.switch_to.frame(payment_frame)
        except TimeoutException:
            pass

        # [🍜] Click the [order] button.
        try:
            time.sleep(0.5)
            WebDriverWait(
                ctx, 20, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(@class,'payment-btn')]")
                )
            ).click()
        except TimeoutException:
            ctx.switch_to.default_content()
            return

        # [🍜] 捕获隐藏在订单中的人机挑战，仅在周免游戏中出现。
        if self._armor.fall_in_captcha_runtime(ctx):
            self.assert_.wrong_driver(ctx, "任务中断，请使用挑战者上下文处理意外弹出的人机验证。")
            try:
                self._armor.anti_hcaptcha(ctx, door="free")
            except (ChallengeReset, WebDriverException):
                pass

        # [🍜] Switch to default iframe.
        ctx.switch_to.default_content()
        ctx.refresh()

    def _unreal_get_free_resource(self, ctx, ctx_cookies):
        """获取虚幻商城的本月免费内容"""
        if not ctx_cookies:
            raise CookieExpired(self.assert_.COOKIE_EXPIRED)

        _loop_start = time.time()
        init = True
        while True:
            # [🚀] 重载身份令牌
            self._reset_page(
                ctx=ctx,
                page_link=self.URL_UNREAL_MONTH,
                ctx_cookies=ctx_cookies,
                _auth_str="unreal",
            )

            # [🚀] 等待资源加载
            self.assert_.unreal_resource_load(ctx)

            # [🚀] 从虚幻商店购物车激活订单
            self.result = self._unreal_activate_payment(ctx, init=init)
            if self.result != self.assert_.GAME_PENDING:
                if self.result == self.assert_.ASSERT_OBJECT_EXCEPTION:
                    continue
                break

            # [🚀] 处理商品订单
            self._unreal_handle_payment(ctx)

            # [🚀] 更新上下文状态
            init = False
            self.assert_.timeout(_loop_start, self.loop_timeout)
