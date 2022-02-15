# -*- coding: utf-8 -*-
# Time       : 2022/1/17 13:50
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import locale
import os.path
import sys
from hashlib import sha256
from typing import List, Optional

import cloudscraper
import yaml

from services.settings import logger
from services.utils import (
    ToolBox,
    get_ctx,
    get_challenge_ctx,
    ChallengeReset,
    ChallengeTimeout,
)
from .core import AwesomeFreeMan
from .exceptions import (
    AssertTimeout,
    SwitchContext,
    PaymentException,
    AuthException,
    UnableToGet,
)


class CookieManager(AwesomeFreeMan):
    """管理上下文身份令牌"""

    def __init__(self):
        super().__init__()

        self.action_name = "CookieManager"

    def _t(self) -> str:
        return (
            sha256(self.email[-3::-1].encode("utf-8")).hexdigest() if self.email else ""
        )

    def load_ctx_cookies(self) -> Optional[List[dict]]:
        """
        载入本地缓存的身份令牌。

        :return:
        """
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
        """
        在本地缓存身份令牌。

        :param ctx_cookies:
        :return:
        """
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
        """
        检测 COOKIE 是否有效

        :param ctx_cookies: 若不指定则将工作目录 cookies 视为 ctx_cookies
        :return:
        """
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

    def refresh_ctx_cookies(self, silence: bool = True) -> Optional[bool]:
        """
        更新上下文身份信息

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

        if "linux" in sys.platform and "zh_CN" not in locale.getdefaultlocale():
            print(
                "Please modify the locale `LANG` before executing the scaffold command."
            )
            print("such as: `export LC_ALL=zh_CN.UTF8 && python3 main.py claim`")
            sys.exit()

        # {{< Insert Challenger Context >}}
        ctx = get_challenge_ctx(silence=silence)
        try:
            for _ in range(8):
                # Enter the account information and jump to the man-machine challenge page.
                self._login(self.email, self.password, ctx=ctx)

                # Assert if you are caught in a man-machine challenge.
                try:
                    fallen = self._armor.fall_in_captcha_login(ctx=ctx)
                except AssertTimeout:
                    continue
                else:
                    # Approved.
                    if not fallen:
                        break

                    # Winter is coming, so hear me roar!
                    response = self._armor.anti_hcaptcha(ctx, door="login")
                    if response:
                        break
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
        except (AuthException, ChallengeTimeout) as error:
            logger.critical(
                ToolBox.runtime_report(
                    motive="SKIP", action_name=self.action_name, message=error.msg
                )
            )
            return False
        else:
            # Store contextual authentication information.
            self.save_ctx_cookies(ctx_cookies=ctx.get_cookies())
            return self.is_available_cookie(ctx_cookies=ctx.get_cookies())
        finally:
            ctx.quit()
        # {{< Done >}}

        return True


class Bricklayer(AwesomeFreeMan):
    """常驻免费游戏的认领逻辑"""

    def __init__(self, silence: bool = None):
        super().__init__()
        self.silence = True if silence is None else silence

        self.action_name = "AwesomeFreeMan"

        self.cookie_manager = CookieManager()

    def get_free_game(
        self,
        page_link: str = None,
        ctx_cookies: List[dict] = None,
        refresh: bool = True,
        challenge: Optional[bool] = None,
    ) -> Optional[bool]:
        """
        获取免费游戏

        部署后必须传输有效的 `page_link` 参数。
        :param challenge:
        :param page_link: 游戏购买页链接 zh-CN
        :param refresh: 当 COOKIE 失效时主动刷新 COOKIE
        :param ctx_cookies:
        :return:
        """
        page_link = self.URL_FREE_GAME_TEST if page_link is None else page_link
        ctx_cookies = (
            self.cookie_manager.load_ctx_cookies()
            if ctx_cookies is None
            else ctx_cookies
        )

        # [🚀] 验证 COOKIE
        # 请勿在并发环境下 让上下文驱动陷入到不得不更新 COOKIE 的陷阱之中。
        if not ctx_cookies or not self.cookie_manager.is_available_cookie(
            ctx_cookies=ctx_cookies
        ):
            if refresh:
                self.cookie_manager.refresh_ctx_cookies()
                ctx_cookies = self.cookie_manager.load_ctx_cookies()
            else:
                logger.error(
                    ToolBox.runtime_report(
                        motive="QUIT",
                        action_name=self.action_name,
                        message="Cookie 已过期，任务已退出。",
                    )
                )
                return False

        # [🚀] 常驻免费（General）周免（Challenge）
        ctx = get_challenge_ctx(self.silence) if challenge else get_ctx(self.silence)
        try:
            self._get_free_game(page_link=page_link, api_cookies=ctx_cookies, ctx=ctx)
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
        except PaymentException as error:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT",
                    action_name=self.action_name,
                    message="🚧 订单异常",
                    type=f"PaymentException {error}".strip(),
                    url=page_link,
                )
            )
        except AuthException as error:
            logger.critical(
                ToolBox.runtime_report(
                    motive="SKIP", action_name=self.action_name, message=error.msg
                )
            )
            return False
        finally:
            ctx.quit()

        return True
