# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import time
import urllib.request
from typing import List, Optional, NoReturn

from selenium.common.exceptions import (
    TimeoutException,
    ElementNotVisibleException,
    WebDriverException,
    ElementClickInterceptedException,
    NoSuchElementException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from undetected_chromedriver import Chrome

from config import (
    USER_EMAIL,
    USER_PASSWORD
)
from services.settings import (
    logger,
    DIR_COOKIES,
    DIR_CHALLENGE,
    DIR_MODEL
)
from services.utils import (
    YOLO,
    ToolBox,
    ArmorCaptcha,
    CoroutineSpeedup,
    ChallengeReset,
)
from .exceptions import (
    AssertTimeout,
    UnableToGet,
    CookieExpired,
    SwitchContext,
    PaymentException,
    AuthException,
)

# 显示人机挑战的DEBUG日志
ARMOR_DEBUG = True


class ArmorUtils(ArmorCaptcha):
    """人机对抗模组"""

    def __init__(self, debug: bool = ARMOR_DEBUG):
        super(ArmorUtils, self).__init__(dir_workspace=DIR_CHALLENGE, debug=debug)

        # 重定向工作空间
        self.model = YOLO(DIR_MODEL)

    @staticmethod
    def fall_in_captcha_login(ctx: Chrome) -> Optional[bool]:
        """
        判断在登录时是否遇到人机挑战

        :param ctx:
        :return: True：已进入人机验证页面，False：跳转到个人主页
        """
        threshold_timeout = 35
        start = time.time()
        flag_ = ctx.current_url
        while True:
            if ctx.current_url != flag_:
                return False

            if time.time() - start > threshold_timeout:
                raise AssertTimeout("任务超时：判断是否陷入人机验证")

            try:
                ctx.switch_to.frame(ctx.find_element(By.XPATH, f"//iframe[@id='talon_frame_login_prod']"))
                ctx.switch_to.frame(ctx.find_element(By.XPATH, "//iframe[contains(@title,'content')]"))
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

        :param ctx:
        :return:
        """
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='talon_frame_checkout_free_prod']"))
            )
            return True
        except TimeoutException:
            return False

    def download_images(self) -> None:
        """
        植入协程框架加速下载。

        :return:
        """

        class ImageDownloader(CoroutineSpeedup):
            def __init__(self, docker=None):
                super(ImageDownloader, self).__init__(docker=docker)

            def control_driver(self, task, *args, **kwargs):
                path_challenge_img, url = task
                urllib.request.urlretrieve(url, path_challenge_img)

        self.log(message="下载挑战图片")
        workspace_ = self._init_workspace()
        docker_ = []
        for alias_, url_ in self.alias2url.items():
            path_challenge_img_ = os.path.join(workspace_, f"{alias_}.png")
            self.alias2path.update({alias_: path_challenge_img_})
            docker_.append((path_challenge_img_, url_))
        downloader = ImageDownloader(docker=docker_)
        downloader.go(power=9)

        self.runtime_workspace = workspace_

    def challenge_success(self, ctx: Chrome, init: bool = True) -> Optional[bool]:
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

        def _runtime_assert():
            flag = ctx.current_url
            if init:
                try:
                    time.sleep(1.5)
                    WebDriverWait(ctx, 2, ignored_exceptions=WebDriverException).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@class='task-image']"))
                    )
                except TimeoutException:
                    pass
                else:
                    self.log("挑战继续")
                    return False

            try:
                challenge_reset = WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@class='MuiAlert-message']"))
                )
            except TimeoutException:
                try:
                    WebDriverWait(ctx, 8).until(EC.url_changes(flag))
                except TimeoutException:
                    self.log("断言超时，挑战继续")
                    return False
                else:
                    # 如果没有遇到双重认证，说明挑战成功
                    return True
            else:
                self.log("挑战失败，需要重置挑战")
                challenge_reset.click()
                raise ChallengeReset

        result = _runtime_assert()
        if result:
            if "id/login/mfa" in ctx.current_url:
                raise AuthException("遭遇意外的 2FA 双重认证，人机挑战已退出。")
            self.log("挑战成功")
        return result

    def anti_hcaptcha(self, ctx: Chrome, door: str = "login") -> Optional[bool]:
        """
        Handle hcaptcha challenge

        ## Reference

        M. I. Hossen and X. Hei, "A Low-Cost Attack against the hCaptcha System," 2021 IEEE Security
        and Privacy Workshops (SPW), 2021, pp. 422-431, doi: 10.1109/SPW53761.2021.00061.

        > ps:该篇文章中的部分内容已过时，现在 hcaptcha challenge 远没有作者说的那么容易应付。

        :param door:
        :param ctx:
        :return:
        """
        iframe_mapping = {
            "login": "talon_frame_login_prod",
            "free": "talon_frame_checkout_free_prod"
        }
        """
        [👻] 进入人机挑战关卡
        _______________
        """
        ctx.switch_to.frame(WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.XPATH, f"//iframe[@id='{iframe_mapping[door]}']"))
        ))

        ctx.switch_to.frame(WebDriverWait(ctx, 5, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title,'content')]"))
        ))

        """
        [👻] 获取挑战图片
        _______________
        多轮验证标签不会改变
        """
        self.get_label(ctx)
        if self.tactical_retreat():
            ctx.switch_to.default_content()
            return False

        """
        [👻] 人机挑战！
        _______________
        """
        try:
            for index in range(2):
                self.mark_samples(ctx)

                self.download_images()

                self.challenge(ctx, model=self.model)

                result = self.challenge_success(ctx, not bool(index))

                # 仅一轮测试就通过
                if index == 0 and result:
                    break
                # 断言超时
                if index == 1 and result is False:
                    ctx.switch_to.default_content()
                    return False
        except ChallengeReset:
            ctx.switch_to.default_content()
            return self.anti_hcaptcha(ctx)
        else:
            # 回到主线剧情
            ctx.switch_to.default_content()
            return True


class AwesomeFreeMan:
    """白嫖人的基础设施"""

    def __init__(self):
        """定义了一系列领取免费游戏所涉及到的浏览器操作。"""

        # 实体对象参数
        self.action_name = "BaseAction"
        self.email, self.password = USER_EMAIL, USER_PASSWORD

        # 驱动参数
        self.path_ctx_cookies = os.path.join(DIR_COOKIES, "ctx_cookies.yaml")
        self.loop_timeout = 300

        # 特征指令/简易错误
        self.COOKIE_EXPIRED = "饼干过期了"
        self.ASSERT_OBJECT_EXCEPTION = "无效的断言对象"
        self.GAME_OK = "游戏在库"
        self.GAME_FETCH = "游戏未在库/可获取"

        # 操作对象参数
        self.URL_LOGIN = "https://www.epicgames.com/id/login/epic?lang=zh-CN"
        self.URL_FREE_GAME_TEST = "https://www.epicgames.com/store/zh-CN/p/galactic-civilizations-iii"
        self.URL_CHECK_COOKIE = "https://www.epicgames.com/store/zh-CN/"
        self.URL_ACCOUNT_PERSONAL = "https://www.epicgames.com/account/personal"

        # 注册拦截机
        self._armor = ArmorUtils()

    def _assert_purchase_status(self, ctx: Chrome, page_link: str) -> Optional[str]:
        """
        断言当前上下文页面的游戏的在库状态。

        :param ctx:
        :return:
        """
        # 捕获按钮对象，根据按钮上浮动的提示信息断言游戏在库状态
        time.sleep(2)
        assert_obj = WebDriverWait(ctx, 30, ignored_exceptions=ElementNotVisibleException).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//span[@data-component='PurchaseCTA']//span[@data-component='Message']"))
        )
        # TODO 此处需要一个错误类型表示获取了空的按钮对象
        if not assert_obj:
            return self.ASSERT_OBJECT_EXCEPTION

        # 游戏对象
        game_obj = WebDriverWait(ctx, 30, ignored_exceptions=ElementNotVisibleException).until(
            EC.visibility_of_element_located((By.XPATH, "//h1"))
        )

        if game_obj.text[-1] == "。":
            logger.warning(ToolBox.runtime_report(
                motive="SKIP",
                action_name=self.action_name,
                message=f"🚫 {game_obj.text}",
                url=page_link
            ))
            return self.ASSERT_OBJECT_EXCEPTION

        if "已在游戏库中" in assert_obj.text:
            logger.info(ToolBox.runtime_report(
                motive="GET",
                action_name=self.action_name,
                message="🛴 游戏已在库",
                game=f"『{game_obj.text}』"
            ))
            return self.GAME_OK

        if "获取" in assert_obj.text:
            logger.success(ToolBox.runtime_report(
                motive="GET",
                action_name=self.action_name,
                message="🚀 发现新游戏",
                game=f"『{game_obj.text}』"
            ))
            return self.GAME_FETCH

        if "购买" in assert_obj.text:
            logger.warning(ToolBox.runtime_report(
                motive="SKIP",
                action_name=self.action_name,
                message="🚧 这不是免费游戏",
                game=f"『{game_obj.text}』"
            ))
            return self.ASSERT_OBJECT_EXCEPTION

        return self.ASSERT_OBJECT_EXCEPTION

    @staticmethod
    def _assert_surprise_license(ctx: Chrome) -> None:
        """
        新用户首次购买游戏需要处理许可协议书

        :param ctx:
        :return:
        """
        try:
            surprise_obj = WebDriverWait(ctx, 5, ignored_exceptions=ElementNotVisibleException).until(
                EC.presence_of_element_located((By.XPATH, "//label//span[@data-component='Message']"))
            )
        except TimeoutException:
            return
        else:
            if surprise_obj.text == "我已阅读并同意最终用户许可协议书":
                time.sleep(2)
                try:
                    # 勾选协议
                    WebDriverWait(ctx, 5, ignored_exceptions=ElementClickInterceptedException).until(
                        EC.element_to_be_clickable((By.ID, "agree"))
                    ).click()

                    # 点击接受
                    WebDriverWait(ctx, 5, ignored_exceptions=ElementClickInterceptedException).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@class='css-1llvwt3']"))
                    ).click()
                # 窗口渲染出来后因不可抗力因素自然消解
                except TimeoutException:  # noqa
                    pass

    @staticmethod
    def _assert_fall_in_captcha_runtime(ctx: Chrome) -> Optional[bool]:
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='talon_frame_checkout_free_prod']"))
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _assert_surprise_warning(ctx: Chrome) -> Optional[bool]:
        """
        处理意外的遮挡消息。

        这是一个没有意义的操作，但无可奈何，需要更多的测试。
        :param ctx:
        :return:
        """
        surprise_warning = ctx.find_element(By.TAG_NAME, "h1").text

        if "成人内容" in surprise_warning:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@class='css-n9sjaa']"))
            ).click()
            return True

        if "内容品当前在您所在平台或地区不可用。" in surprise_warning:
            raise UnableToGet(surprise_warning)

        return False

    def _handle_payment(self, ctx: Chrome) -> None:
        """
        处理游戏订单

        :param ctx:
        :return:
        """
        # Switch to Payment iframe.
        try:
            payment_frame = WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='webPurchaseContainer']//iframe"))
            )
        except TimeoutException:
            warning_layout = WebDriverWait(ctx, 10, ignored_exceptions=WebDriverException).until(
                EC.visibility_of_element_located((By.XPATH, "//div[@data-component='WarningLayout']"))
            )
            if "依旧要购买吗" in warning_layout.text:
                ctx.switch_to.default_content()
                return
        else:
            ctx.switch_to.frame(payment_frame)

        # Click the [Accept Agreement] confirmation box.
        for _ in range(4):
            try:
                WebDriverWait(ctx, 10, ignored_exceptions=ElementClickInterceptedException).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@class='payment-check-box']"))
                ).click()
                break
            except TimeoutException:  # noqa
                try:
                    ctx.find_element(By.XPATH, "//div[contains(@class,'payment-check-box')]").click()
                except NoSuchElementException:
                    warning_ = ctx.find_element(By.TAG_NAME, "h2").text
                    raise PaymentException(warning_)

        # Click the [order] button.
        time.sleep(0.5)
        WebDriverWait(ctx, 60, ignored_exceptions=ElementClickInterceptedException).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class,'payment-btn')]"))
        ).click()

        # 在运行时处理人机挑战是非常困难的事情。
        # 因为绝大多数的人机挑战都会试着识别驱动数据，若咱没使用专门处理人机挑战的驱动上下文，
        # 会诱发一系列影响系统效率的事情，所以此时最好的方法是主动结束任务，切换挑战上下文，重启。
        if self._armor.fall_in_captcha_runtime(ctx):
            if "chrome.webdriver" in str(ctx.__class__):
                raise SwitchContext("任务中断，请使用挑战者上下文处理意外弹出的人机验证。")
            try:
                self._armor.anti_hcaptcha(ctx, door="free")
            except ChallengeReset:
                pass

        # Switch to default iframe.
        ctx.switch_to.default_content()

    def _activate_payment(self, api: Chrome) -> Optional[bool]:
        """
        激活游戏订单

        :param api:
        :return:
        """
        for _ in range(5):
            try:
                WebDriverWait(api, 5, ignored_exceptions=ElementClickInterceptedException).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='purchase-cta-button']"))
                ).click()
                return True
            except TimeoutException:
                continue
            except ElementClickInterceptedException:
                try:
                    if self._assert_surprise_warning(api) is True:
                        continue
                except UnableToGet:
                    return False

    def _assert_timeout(self, loop_start: float) -> NoReturn:
        if time.time() - loop_start > self.loop_timeout:
            raise AssertTimeout

    def _login(self, email: str, password: str, ctx: Chrome) -> None:
        """
        作为被动方式，登陆账号，刷新 identity token。

        此函数不应被主动调用，应当作为 refresh identity token / Challenge 的辅助函数。
        :param ctx:
        :param email:
        :param password:
        :return:
        """
        ctx.get(self.URL_LOGIN)

        WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.ID, "email"))
        ).send_keys(email)

        WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.ID, "password"))
        ).send_keys(password)

        WebDriverWait(ctx, 60, ignored_exceptions=ElementClickInterceptedException).until(
            EC.element_to_be_clickable((By.ID, "sign-in"))
        ).click()

    def _get_free_game(self, page_link: str, api_cookies: List[dict], ctx: Chrome) -> None:
        """
        获取免费游戏

        需要加载cookie后使用，避免不必要的麻烦。
        :param page_link:
        :param api_cookies:
        :param ctx:
        :return:
        """
        if not api_cookies:
            raise CookieExpired(self.COOKIE_EXPIRED)

        _loop_start = time.time()
        while True:
            self._assert_timeout(_loop_start)
            """
            [🚀] 重载COOKIE
            _______________
            - InvalidCookieDomainException：需要两次 GET 重载 cookie relative domain
            """
            ctx.get(page_link)
            for cookie_dict in api_cookies:
                ctx.add_cookie(cookie_dict)
            ctx.get(page_link)

            """
            [🚀] 断言游戏的在库状态
            _______________
            """
            result = self._assert_purchase_status(ctx, page_link)
            if result != self.GAME_FETCH:
                break

            """
            [🚀] 激活游戏订单
            _______________
            """
            self._activate_payment(ctx)

            """
            [🚀] 新用户首次购买游戏需要处理许可协议书
            _______________
            """
            self._assert_surprise_license(ctx)

            """
            [🚀] 处理游戏订单
            _______________
            """
            self._handle_payment(ctx)
