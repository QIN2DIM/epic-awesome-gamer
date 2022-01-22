# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import time
import urllib.request
from hashlib import sha256
from typing import List, NoReturn

import cloudscraper
import yaml
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

from config import USER_EMAIL, USER_PASSWORD
from services.settings import logger, DIR_COOKIES, DIR_CHALLENGE, DIR_MODEL
from services.utils import (
    ToolBox, ArmorCaptcha, CoroutineSpeedup, YOLO,
    get_ctx, get_challenge_ctx, ChallengeReset,

)
from .exceptions import (
    AssertTimeout,
    UnableToGet,
    CookieExpired,
    SwitchContext,
    PaymentException
)

# 显示人机挑战的DEBUG日志
ARMOR_DEBUG = True


class ArmorUtils(ArmorCaptcha):
    """人机对抗模组"""

    def __init__(self, debug: bool = ARMOR_DEBUG):
        super(ArmorUtils, self).__init__(dir_workspace=DIR_CHALLENGE, debug=debug)

        self.model = YOLO(DIR_MODEL)

    @staticmethod
    def fall_in_captcha_login(ctx: Chrome) -> bool:
        """
        判断是否陷入人机验证

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
    def fall_in_captcha_runtime(ctx: Chrome) -> bool:
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='talon_frame_checkout_free_prod']"))
            )
            return True
        except TimeoutException:
            return False

    def download_images(self):
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

    def anti_hcaptcha(self, ctx: Chrome, door: str = "login"):
        """
        
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

                result = self._challenge_success(ctx, not bool(index))

                # 仅一轮测试就通过
                if index == 0 and result:
                    break
                # 断言超时
                if index == 1 and result is False:
                    ctx.switch_to.default_content()
                    return
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

    def _assert_purchase_status(self, ctx: Chrome, page_link: str) -> str:
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
    def _assert_surprise_license(ctx: Chrome):
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
    def _assert_fall_in_captcha_runtime(ctx: Chrome) -> bool:
        try:
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='talon_frame_checkout_free_prod']"))
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _assert_surprise_warning(ctx: Chrome) -> bool:
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

    def _handle_payment(self, ctx: Chrome):
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
                return True
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

    def _activate_payment(self, api: Chrome):
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

    def _assert_timeout(self, loop_start: float):
        if time.time() - loop_start > self.loop_timeout:
            raise AssertTimeout

    def _get_free_game(self, page_link: str, api_cookies: List[dict], ctx: Chrome):
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

    def _login(self, email: str, password: str, ctx: Chrome):
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


class CookieManager(AwesomeFreeMan):
    def __init__(self):
        super(CookieManager, self).__init__()

        self.action_name = "CookieManager"

    def _t(self) -> str:
        return sha256(self.email[-3::-1].encode("utf-8")).hexdigest() if self.email else ""

    def load_ctx_cookies(self) -> List[dict]:
        """
        载入本地缓存的身份令牌。

        :return:
        """
        if not os.path.exists(self.path_ctx_cookies):
            return []

        with open(self.path_ctx_cookies, "r", encoding='utf8') as f:
            data: dict = yaml.safe_load(f)

        ctx_cookies = data.get(self._t(), []) if type(data) == dict else []
        if not ctx_cookies:
            return []

        logger.debug(ToolBox.runtime_report(
            motive="LOAD",
            action_name=self.action_name,
            message="Overload Context Cookie."
        ))

        return ctx_cookies

    def save_ctx_cookies(self, ctx_cookies: List[dict]) -> NoReturn:
        """
        在本地缓存身份令牌。

        :param ctx_cookies:
        :return:
        """
        _data = {}

        if os.path.exists(self.path_ctx_cookies):
            with open(self.path_ctx_cookies, "r", encoding='utf8') as f:
                stream: dict = yaml.safe_load(f)
                _data = _data if type(stream) != dict else stream

        _data.update({self._t(): ctx_cookies})

        with open(self.path_ctx_cookies, "w", encoding="utf8") as f:
            yaml.dump(_data, f)

        logger.debug(ToolBox.runtime_report(
            motive="SAVE",
            action_name=self.action_name,
            message="Update Context Cookie."
        ))

    def is_available_cookie(self, ctx_cookies: List[dict] = None) -> bool:
        """
        检测 COOKIE 是否有效

        :param ctx_cookies: 若不指定则将工作目录 cookies 视为 ctx_cookies
        :return:
        """
        ctx_cookies = self.load_ctx_cookies() if ctx_cookies is None else ctx_cookies
        headers = {"cookie": ToolBox.transfer_cookies(ctx_cookies)}

        scraper = cloudscraper.create_scraper()
        response = scraper.get(self.URL_ACCOUNT_PERSONAL, headers=headers, allow_redirects=False)
        if response.status_code == 200:
            return True
        return False

    def refresh_ctx_cookies(self, verify: bool = True, ctx_cookies: List[dict] = None) -> NoReturn:
        """
        更新上下文身份信息

        :return:
        """

        # {{< Check Context Cookie Validity >}}
        if verify:
            if self.is_available_cookie(ctx_cookies=ctx_cookies):
                logger.success(ToolBox.runtime_report(
                    motive="CHECK",
                    action_name=self.action_name,
                    message="The identity token is valid."
                ))
                return True
        # {{< Done >}}

        # {{< Insert Challenger Context >}}
        ctx = get_challenge_ctx(silence=False)
        try:
            for _ in range(8):
                # Enter the account information and jump to the man-machine challenge page.
                self._login(self.email, self.password, ctx=ctx)

                # Assert if you are caught in a man-machine challenge.
                try:
                    fallen = self._armor.fall_in_captcha_login(ctx=ctx)
                except AssertTimeout:
                    pass
                else:
                    # Approved.
                    if not fallen:
                        break

                    # Winter is coming, so hear me roar!
                    response = self._armor.anti_hcaptcha(ctx)
                    if response:
                        break
            else:
                logger.critical(ToolBox.runtime_report(
                    motive="MISS",
                    action_name=self.action_name,
                    message="Identity token update failed."
                ))
                return False

            # Store contextual authentication information.
            self.save_ctx_cookies(ctx_cookies=ctx.get_cookies())
        finally:
            if ctx:
                ctx.close()
                ctx.quit()
        # {{< Done >}}


class Bricklayer(AwesomeFreeMan):
    def __init__(self, silence: bool = None):
        super(Bricklayer, self).__init__()
        self.silence = True if silence is None else silence

        self.action_name = "AwesomeFreeMan"

        self.cookie_manager = CookieManager()

    def get_free_game(
            self,
            page_link: str = None,
            ctx_cookies: List[dict] = None,
            refresh: bool = True,
            ctx: Chrome = None,
    ):
        """
        获取免费游戏

        部署后必须传输有效的 `page_link` 参数。
        :param ctx:
        :param page_link: 游戏购买页链接 zh-CN
        :param refresh: 当 COOKIE 失效时主动刷新 COOKIE
        :param ctx_cookies:
        :return:
        """
        page_link = self.URL_FREE_GAME_TEST if page_link is None else page_link
        ctx_cookies = self.cookie_manager.load_ctx_cookies() if ctx_cookies is None else ctx_cookies
        ctx = get_ctx(silence=self.silence) if ctx is None else ctx
        """
        [🚀] 验证 COOKIE
        _______________
        请勿在并发环境下 让上下文驱动陷入到不得不更新 COOKIE 的陷阱之中。
        """
        if not ctx_cookies or not self.cookie_manager.is_available_cookie(ctx_cookies=ctx_cookies):
            if refresh:
                self.cookie_manager.refresh_ctx_cookies(verify=False)
                ctx_cookies = self.cookie_manager.load_ctx_cookies()
            else:
                logger.error(ToolBox.runtime_report(
                    motive="QUIT",
                    action_name=self.action_name,
                    message="Cookie 已过期，任务已退出。"
                ))
                return False

        """
        [🚀] 使用普通级别的上下文获取免费游戏
        _______________
        """
        try:
            self._get_free_game(page_link=page_link, api_cookies=ctx_cookies, ctx=ctx)
        except AssertTimeout:
            logger.debug(ToolBox.runtime_report(
                motive="QUIT",
                action_name=self.action_name,
                message="循环断言超时，任务退出。"
            ))
        except SwitchContext as e:
            logger.warning(ToolBox.runtime_report(
                motive="SWITCH",
                action_name=self.action_name,
                message="尝试切换驱动上下文进行人机挑战",
                error=e,
                url=page_link,
            ))
            ctx.quit()
            return self.get_free_game(
                page_link=page_link,
                ctx_cookies=ctx_cookies,
                ctx=get_challenge_ctx(self.silence)
            )
        except PaymentException as e:
            logger.debug(ToolBox.runtime_report(
                motive="QUIT",
                action_name=self.action_name,
                message=e.msg,
                url=page_link,
            ))
        finally:
            if ctx:
                ctx.quit()
