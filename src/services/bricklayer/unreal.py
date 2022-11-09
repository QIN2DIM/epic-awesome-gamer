# -*- coding: utf-8 -*-
# Time       : 2022/4/6 19:52
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing

import requests
from bs4 import BeautifulSoup
from loguru import logger
from playwright.sync_api import Page

from services.utils.toolbox import ToolBox
from .core import CookieManager, EpicAwesomeGamer


class UnrealClaimer(EpicAwesomeGamer):
    """虚幻商城月供砖家"""

    URL_UNREAL_HOME = "https://www.unrealengine.com"
    URL_UNREAL_STORE = "https://www.unrealengine.com/marketplace/zh-CN/store"
    URL_UNREAL_ASSETS = "https://www.unrealengine.com/marketplace/zh-CN/assets"
    URL_FREE_FOR_THE_MONTH = (
        URL_UNREAL_ASSETS + "?count=20&sortBy=effectiveDate&sortDir=DESC&start=0&tag=4910"
    )
    URL_FREE_ALL = (
        URL_UNREAL_ASSETS
        + "?count=20&priceRange=%5B0%2C0%5D&sortBy=effectiveDate&sortDir=DESC&start=0"
    )

    def __init__(self, email: str, password: str):
        super().__init__(email=email, password=password)
        self.result = ""
        self.action_name = "UnrealClaimer"
        self.cookie_manager = CookieManager(auth_str="unreal", email=email, password=password)

    def get_promotions(
        self, ctx_cookies: typing.Optional[typing.List[dict]] = None
    ) -> typing.List[typing.Dict[str, typing.Union[str, bool]]]:
        """领取任务后审查资源的在库状态"""
        headers = {"cookie": ToolBox.transfer_cookies(ctx_cookies) if ctx_cookies else ""}
        response = requests.get(self.URL_FREE_FOR_THE_MONTH, headers=headers, allow_redirects=False)

        if not ctx_cookies:
            logger.warning(f">> DROP [{self.action_name}] 无效的身份令牌，即将返回空数据")
        if response.status_code != 200:
            logger.error(f">> SKIP [{self.action_name}] 身份令牌已过期，无法获取有效的月供内容在库状态")
            return []

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find("div", class_="asset-list-group").find_all("article")
        except AttributeError:
            logger.critical(f">> CRASH [{self.action_name}] 虚幻商店月供内容页元素改变或加载异常")
            return []
        else:
            if not articles:
                logger.critical(f">> MISS [{self.action_name}] 虚幻商店月供内容或为空，请复查")
                return []
            # Implement Promotion Interface
            details = [
                {
                    "url": f"{self.URL_UNREAL_HOME}{article.h3.a['href']}",
                    "title": article.find("h3").text,
                    "image_url": "",
                    "in_library": "撰写评论" in article.text,
                }
                for article in articles
                if "100%OFF" in article.text
            ]
            return details

    def get_free_content(self, page: Page):
        """获取虚幻商城的本月免费内容"""
        for i in range(2):
            # [🚀] 从虚幻商店购物车激活订单
            self.result = self.unreal_activate_payment(page, init=not i)
            # [🚀] 处理购物车订单
            if self.result == self.assert_util.GAME_PENDING:
                self.unreal_handle_payment(page)
            elif self.result in (self.assert_util.GAME_OK, self.assert_util.GAME_CLAIM):
                return self.result
            page.wait_for_timeout(2000)
