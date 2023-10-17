# -*- coding: utf-8 -*-
# Time       : 2023/10/17 23:24
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
from dataclasses import dataclass

from hcaptcha_challenger.agents import AgentT
from playwright.async_api import Page


@dataclass
class AgentG(AgentT):
    HOOK_PURCHASE = "//div[@id='webPurchaseContainer']//iframe"
    HOOK_CHECKBOX = "//iframe[contains(@title, 'checkbox for hCaptcha')]"
    HOOK_CHALLENGE = "//iframe[contains(@title, 'hCaptcha challenge')]"

    def _switch_to_challenge_frame(self, page: Page, window: str = "login", **kwargs):
        if window == "login":
            hook_login_challenge = (
                f"//div[@id='h_captcha_challenge_login_prod']{self.HOOK_CHALLENGE}"
            )
            frame_challenge = page.frame_locator(hook_login_challenge)
        else:
            frame_purchase = page.frame_locator(self.HOOK_PURCHASE)
            frame_challenge = frame_purchase.frame_locator(self.HOOK_CHALLENGE)

        return frame_challenge
