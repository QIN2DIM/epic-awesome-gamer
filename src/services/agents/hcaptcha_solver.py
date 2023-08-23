# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:15
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Tuple

from hcaptcha_challenger.agents.exceptions import AuthMFA, AuthUnknownException, LoginException
from hcaptcha_challenger.agents.exceptions import ChallengePassed
from hcaptcha_challenger.agents.playwright import PlaywrightAgent
from hcaptcha_challenger.agents.skeleton import Status
from loguru import logger
from playwright.sync_api import Error as NinjaError
from playwright.sync_api import Page, FrameLocator
from playwright.sync_api import TimeoutError as NinjaTimeout


@dataclass
class Radagon(PlaywrightAgent):
    """人机对抗模组"""

    def is_success(
        self,
        page: Page,
        frame_challenge: FrameLocator = None,
        window=None,
        init=True,
        hook_url=None,
        *args,
        **kwargs,
    ) -> Tuple[str, str]:
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
                logger.debug("Checkout - status=再试一次")
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
            return self.status.CHALLENGE_CONTINUE, "继续挑战"
        if is_continue_clickable():
            return self.status.CHALLENGE_CONTINUE, "继续挑战"

        flag = page.url

        if window == "free":
            try:
                page.locator(self.HOOK_PURCHASE).wait_for(state="detached")
                return self.status.CHALLENGE_SUCCESS, "退火成功"
            except NinjaTimeout:
                return self.status.CHALLENGE_RETRY, "決策中斷"
        if window == "login":
            for _ in range(3):
                if hook_url:
                    with suppress(NinjaTimeout):
                        page.wait_for_url(hook_url, timeout=3000)
                        return self.status.CHALLENGE_SUCCESS, "退火成功"
                else:
                    page.wait_for_timeout(2000)
                    if page.url != flag:
                        if "id/login/mfa" not in page.url:
                            return self.status.CHALLENGE_SUCCESS, "退火成功"
                        raise AuthMFA("人机挑战已退出 - error=遭遇意外的 MFA 多重认证")

                mui_typography = page.locator("//h6")
                with suppress(NinjaTimeout):
                    mui_typography.first.wait_for(timeout=1000, state="attached")
                if mui_typography.count() > 1:
                    with suppress(AttributeError):
                        error_text = mui_typography.nth(1).text_content().strip()
                        if "错误回复" in error_text:
                            self.critical_threshold += 1
                            return self.status.CHALLENGE_RETRY, "登入页面错误回复"
                        if "there was a socket open error" in error_text:
                            return self.status.CHALLENGE_RETRY, "there was a socket open error"
                        if self.critical_threshold > 3:
                            logger.debug(f"認證失敗 - {error_text=}")
                            _unknown = AuthUnknownException(msg=error_text)
                            _unknown.report(error_text)
                            raise _unknown

    def anti_hcaptcha(
        self, page: Page, window: str = "login", recur_url=None, *args, **kwargs
    ) -> bool | str:
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
                page.wait_for_timeout(2000)
                # [👻] 获取挑战标签
                self.get_label(frame_challenge)
                # [👻] 編排定位器索引
                self.mark_samples(frame_challenge)
                # [👻] 拉取挑戰圖片
                self.download_images()
                # [👻] 滤除无法处理的挑战类别
                if "please click on the" in self._label.lower():
                    return self.status.CHALLENGE_BACKCALL
                if not self._label_alias.get(self._label):
                    return self.status.CHALLENGE_BACKCALL
                # [👻] 注册解决方案
                # 根据挑战类型自动匹配不同的模型
                model = self.match_solution()
                # [👻] 識別|點擊|提交
                self.challenge(frame_challenge, model=model)
                # [👻] 輪詢控制臺響應
                with suppress(TypeError):
                    result, message = self.is_success(
                        page, frame_challenge, window=window, init=not i, hook_url=recur_url
                    )
                    logger.debug("获取响应", desc=f"{message}({result})")
                    if result in [
                        self.status.CHALLENGE_SUCCESS,
                        self.status.CHALLENGE_CRASH,
                        self.status.CHALLENGE_RETRY,
                    ]:
                        return result
                    page.wait_for_timeout(2000)
        # from::mark_samples url = re.split(r'[(")]', image_style)[2]
        except IndexError:
            return self.anti_hcaptcha(page, window, recur_url)
        except ChallengePassed:
            return self.status.CHALLENGE_SUCCESS
        except Exception as err:
            logger.exception(err)


def is_fall_in_captcha(page: Page) -> str | None:
    """判断在登录时是否遇到人机挑战"""
    logger.info("正在检测隐藏在登录界面的人机挑战...")
    flag = page.url

    for _ in range(15):
        # 控制台信息
        mui_typography = page.locator("//h6")
        with suppress(NinjaTimeout):
            mui_typography.first.wait_for(timeout=2000, state="attached")
            if mui_typography.count() > 1:
                error_text = mui_typography.nth(1).text_content().strip()
                logger.error(f"認證異常", err=error_text)
                if "账号或密码" in error_text:
                    raise LoginException(error_text)
                return Status.AUTH_ERROR
        # 頁面重定向|跳過挑戰
        if page.url != flag:
            logger.info("🥤 跳过人机挑战")
            return Status.AUTH_SUCCESS
        # 多因素判斷
        page.wait_for_timeout(2000)
        with suppress(NinjaError):
            if page.locator(Radagon.HOOK_CHALLENGE).is_visible():
                return Status.AUTH_CHALLENGE
