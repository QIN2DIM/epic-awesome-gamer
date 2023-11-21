# -*- coding: utf-8 -*-
# Time       : 2023/10/17 23:24
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import asyncio
from dataclasses import dataclass

from hcaptcha_challenger.agents import AgentT
from playwright.async_api import Page
from tenacity import *


@dataclass
class AgentG(AgentT):
    HOOK_PURCHASE = "//div[@id='webPurchaseContainer']//iframe"
    HOOK_CHECKBOX = "//iframe[contains(@title, 'checkbox for hCaptcha')]"
    HOOK_CHALLENGE = "//iframe[contains(@title, 'hCaptcha challenge')]"

    def _switch_to_challenge_frame(self, page: Page, window: str = "login", **kwargs):
        if window == "login_prod":
            frame_challenge = page.frame_locator(
                f"//div[@id='h_captcha_challenge_login_prod']{self.HOOK_CHALLENGE}"
            )
        elif window == "email_exists_prod":
            frame_challenge = page.frame_locator(
                f"//div[@id='h_captcha_challenge_email_exists_prod']{self.HOOK_CHALLENGE}"
            )
        else:
            frame_purchase = page.frame_locator(self.HOOK_PURCHASE)
            frame_challenge = frame_purchase.frame_locator(self.HOOK_CHALLENGE)

        return frame_challenge

    @retry(
        retry=retry_if_exception_type(asyncio.QueueEmpty),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(30) | stop_after_attempt(60)),
        reraise=True,
    )
    async def _reset_state(self) -> bool | None:
        self.cr = None
        self.qr = self.qr_queue.get_nowait()

        if not self.qr_queue.empty():
            for _ in range(self.qr_queue.qsize()):
                self.qr = self.qr_queue.get_nowait()

        return True

    @retry(
        retry=retry_if_exception_type(asyncio.QueueEmpty),
        wait=wait_fixed(0.5),
        stop=(stop_after_delay(30) | stop_after_attempt(60)),
        reraise=True,
    )
    async def _is_success(self):
        self.cr = self.cr_queue.get_nowait()

        if not self.cr_queue.empty():
            for _ in range(self.cr_queue.qsize()):
                self.cr = self.cr_queue.get_nowait()

        # Match: Timeout / Loss
        if not self.cr or not self.cr.is_pass:
            return self.status.CHALLENGE_RETRY
        if self.cr.is_pass:
            return self.status.CHALLENGE_SUCCESS
