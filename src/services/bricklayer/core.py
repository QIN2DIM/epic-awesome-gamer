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
    PaymentAutoSubmit
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
                # try:
                #     ctx.switch_to.frame(ctx.find_element(By.XPATH, f"//iframe[@id='talon_frame_login_prod']"))
                # except NoSuchElementException:
                #     pass
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

        def _continue_action():
            try:
                time.sleep(1.5)
                WebDriverWait(ctx, 2, ignored_exceptions=WebDriverException).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@class='task-image']"))
                )
            except TimeoutException:
                return True
            else:
                self.log("挑战继续")
                return False

        flag = ctx.current_url

        # 首轮测试后判断短时间内页内是否存在可点击的拼图元素
        # hcaptcha 最多两轮验证，一般情况下，账号信息有误仅会执行一轮，然后返回登录窗格提示密码错误
        # 其次是被识别为自动化控制，这种情况也是仅执行一轮，回到登录窗格提示“返回数据错误”
        if init and not _continue_action():
            return False

        try:
            challenge_reset = WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='MuiAlert-message']"))
            )
        except TimeoutException:
            # 如果挑战通过，自动跳转至其他页面（也即离开当前网址）
            try:
                WebDriverWait(ctx, 8).until(EC.url_changes(flag))
            # 如果挑战未通过，可能为“账号信息错误”“分数太低”“自动化特征被识别”
            except TimeoutException:
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

        :param door:
        :param ctx:
        :return:
        """
        iframe_mapping = {  # noqa
            "login": "talon_frame_login_prod",
            "free": "talon_frame_checkout_free_prod"
        }
        """
        [👻] 进入人机挑战关卡
        _______________
        """
        # ctx.switch_to.frame(WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
        #     EC.presence_of_element_located((By.XPATH, f"//iframe[@id='{iframe_mapping[door]}']"))
        # ))

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
            deadline = self._assert_the_game(ctx)

            # 挑战者驱动不能并发，如果遇到多个周免游戏，需要顺序处理
            if deadline and "chrome.webdriver" in str(ctx.__class__):
                raise SwitchContext("♻ 任务中断，请使用挑战者上下文领取周免游戏。")

            message = "🚀 发现新游戏" if not deadline else f"💰 发现周免游戏 {deadline}"
            logger.success(ToolBox.runtime_report(
                motive="GET",
                action_name=self.action_name,
                message=message,
                game=f"『{game_obj.text}』"
            ))

            # 领取常驻免费游戏的操作是立即生效的，游戏库中立即可见，而领取周免游戏则存在一定的误判概率。
            # 在非生产环境下，技术模型在完成周免游戏领取的操作后，会在连续时间内反复执行此函数进行游戏在库状态的判断。
            # 但是这类游戏从严格意义上算是促销商品，Epic 后台需要一系列复杂的流水线处理流水/订单消息，
            # 这是个较为耗时的过程，短则几秒，长则几分钟，因此可能会出现日志复刷的问题。

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
            # //iframe[@id='talon_frame_checkout_free_prod']
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title,'content')]"))
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _assert_surprise_warning_purchase(ctx: Chrome) -> Optional[bool]:
        """
        处理弹窗遮挡消息。

        这是一个没有意义的操作，但无可奈何，需要更多的测试。
        :param ctx:
        :return:
        """
        time.sleep(2)

        try:
            surprise_warning = ctx.find_element(By.TAG_NAME, "h1").text
        except NoSuchElementException:
            return True

        if "成人内容" in surprise_warning:
            WebDriverWait(ctx, 2, ignored_exceptions=ElementClickInterceptedException).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='继续']/parent::button"))
            ).click()
            return True
        if "内容品当前在您所在平台或地区不可用。" in surprise_warning:
            raise UnableToGet(surprise_warning)
        return False

    @staticmethod
    def _assert_the_game(ctx: Chrome) -> Optional[str]:
        try:
            deadline = WebDriverWait(ctx, 2, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='css-iqno47']//span"))
            )
            return deadline.text if deadline else ""
        except WebDriverException:  # Timeout
            return ""

    @staticmethod
    def _assert_payment_auto_submit(ctx: Chrome) -> NoReturn:
        try:
            warning_text = WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-component='DownloadMessage']//span"))
            ).text
            if warning_text == "感谢您的购买":
                raise PaymentAutoSubmit
        except TimeoutException:
            pass

    @staticmethod
    def _assert_payment_blocked(ctx: Chrome) -> NoReturn:
        # 需要在 webPurchaseContainer 里执行
        try:
            warning_text = WebDriverWait(ctx, 3, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//h2[@class='payment-blocked__msg']"))
            ).text
            raise PaymentException(warning_text)
        except TimeoutException:
            pass

    def _handle_payment(self, ctx: Chrome) -> None:
        """
        处理游戏订单

        逻辑过于复杂，需要重构。此处为了一套代码涵盖各种情况，做了很多妥协。
        需要针对 周免游戏的订单处理 设计一套执行效率更高的业务模型。
        :param ctx:
        :return:
        """
        # 未弹出订单而直接入库
        self._assert_payment_auto_submit(ctx)

        # Switch to the [Purchase Container] iframe.
        try:
            payment_frame = WebDriverWait(ctx, 5, ignored_exceptions=ElementNotVisibleException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='webPurchaseContainer']//iframe"))
            )
            ctx.switch_to.frame(payment_frame)
        # todo 需要更好的方法处理 Cookie lazy loading 的问题
        except TimeoutException:
            try:
                warning_layout = ctx.find_element(By.XPATH, "//div[@data-component='WarningLayout']")
                warning_text = warning_layout.text
                if "依旧要购买吗" in warning_text:
                    ctx.switch_to.default_content()
                    return
                if "设备不受支持" in warning_text:
                    ctx.find_element(By.XPATH, "//button[@class='css-38hacf']").click()
                else:
                    logger.critical(ToolBox.runtime_report(
                        motive="DANCE",
                        action_name=self.action_name,
                        message="Activating flexible plan...",
                        warning_text=warning_text.split("\n")
                    ))
                    ctx.find_element(By.XPATH, "//button[text()='继续']").click()
                    logger.success(ToolBox.runtime_report(
                        motive="DANCE",
                        action_name=self.action_name,
                        message="Recover the flexible plan",
                        warning_text=warning_text.split("\n")
                    ))
            except NoSuchElementException:
                pass

        # 判断游戏锁区
        self._assert_payment_blocked(ctx)

        # Click the [Accept Agreement] confirmation box.
        try:
            WebDriverWait(ctx, 10, ignored_exceptions=ElementClickInterceptedException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='payment-check-box']"))
            ).click()
        # After the order is activated, the agreement may be checked
        except TimeoutException:
            try:
                WebDriverWait(ctx, 5, ignored_exceptions=ElementClickInterceptedException).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'payment-check-box')]"))
                ).click()
            except TimeoutException:
                pass

        # Click the [order] button.
        try:
            time.sleep(0.5)
            WebDriverWait(ctx, 20, ignored_exceptions=ElementClickInterceptedException).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class,'payment-btn')]"))
            ).click()
        # 之前某一个断言操作有误，订单界面未能按照预期效果出现，在超时范围内重试一次。
        except TimeoutException:
            ctx.switch_to.default_content()
            return

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
        ctx.refresh()

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
            # 加载超时，继续测试
            except TimeoutException:
                continue
            # 出现弹窗遮挡
            except ElementClickInterceptedException:
                try:
                    if self._assert_surprise_warning_purchase(api) is True:
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

    @staticmethod
    def _reset_page(ctx: Chrome, page_link: str, api_cookies):
        ctx.get(page_link)
        for cookie_dict in api_cookies:
            ctx.add_cookie(cookie_dict)
        ctx.get(page_link)

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
        _init = True
        while True:
            """
            [🚀] 重载COOKIE
            _______________
            - InvalidCookieDomainException：需要两次 GET 重载 cookie relative domain
            """
            _api_cookies = api_cookies if _init is True else ctx.get_cookies()
            self._reset_page(ctx=ctx, page_link=page_link, api_cookies=api_cookies)

            """
            [🚀] 断言游戏的在库状态
            _______________
            """
            self._assert_surprise_warning_purchase(ctx)
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

            """
            [🚀] 更新上下文状态
            _______________
            """
            _init = False
            self._assert_timeout(_loop_start)
