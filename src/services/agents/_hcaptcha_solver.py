# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:15
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import os
import re
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Tuple
from urllib.request import getproxies

import hcaptcha_challenger as solver
import httpx
from hcaptcha_challenger.exceptions import ChallengePassed
from loguru import logger
from playwright.sync_api import Error as NinjaError
from playwright.sync_api import Page, FrameLocator
from playwright.sync_api import TimeoutError as NinjaTimeout

from services.bricklayer.exceptions import AuthMFA, AuthUnknownException, LoginException


@dataclass
class Status:
    # <success> Challenge Passed by following the expected
    CHALLENGE_SUCCESS = "success"
    # <continue> Continue the challenge
    CHALLENGE_CONTINUE = "continue"
    # <crash> Failure of the challenge as expected
    CHALLENGE_CRASH = "crash"
    # <retry> Your proxy IP may have been flagged
    CHALLENGE_RETRY = "retry"
    # <refresh> Skip the specified label as expected
    CHALLENGE_REFRESH = "refresh"
    # <backcall> (New Challenge) Types of challenges not yet scheduled
    CHALLENGE_BACKCALL = "backcall"

    AUTH_SUCCESS = "success"
    AUTH_ERROR = "error"
    AUTH_CHALLENGE = "challenge"


class Radagon(solver.HolyChallenger):
    """人机对抗模组"""

    # //iframe[@id='talon_frame_checkout_free_prod']
    HOOK_PURCHASE = "//div[@id='webPurchaseContainer']//iframe"
    HOOK_CHECKBOX = "//iframe[contains(@title, 'checkbox for hCaptcha')]"
    HOOK_CHALLENGE = "//iframe[contains(@title, 'hCaptcha挑战')]"

    def __init__(self):
        super().__init__(
            dir_workspace=solver.project.challenge_cache_dir,
            models_dir=solver.project.models_dir,
            objects_path=solver.project.objects_path,
            debug=False,
            screenshot=False,
            lang="en",
        )
        self.critical_threshold = 3

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
                file.write(httpx.get(url_, proxies=getproxies()).content)
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

    def anti_hcaptcha(self, page: Page, window: str = "login", recur_url=None) -> bool | str:
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
