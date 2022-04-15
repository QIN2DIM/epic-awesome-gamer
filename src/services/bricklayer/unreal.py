# -*- coding: utf-8 -*-
# Time       : 2022/4/6 19:52
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import List, Optional, Dict, Union

from bs4 import BeautifulSoup
from cloudscraper import create_scraper

from services.settings import logger
from services.utils import ToolBox
from .bricklayer import Bricklayer
from .exceptions import AuthException, AssertTimeout


class UnrealClaimer(Bricklayer):
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

    def __init__(self, silence: Optional[bool] = None):
        super().__init__(silence=silence, auth_str="unreal")

    def get_claimer_response(
        self, ctx_cookies: List[dict]
    ) -> List[Dict[str, Union[str, bool]]]:
        """领取任务后审查资源的在库状态"""
        headers = {"cookie": ToolBox.transfer_cookies(ctx_cookies)}
        scraper = create_scraper()
        response = scraper.get(self.URL_FREE_FOR_THE_MONTH, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.find("div", class_="asset-list-group").find_all("article")
        details = [
            {
                "name": article.find("h3").text,
                "status": self.assert_.GAME_OK
                if "撰写评论" in article.text
                else self.assert_.GAME_PENDING,
            }
            for article in articles
        ]

        return details

    def get_free_unreal_content(self, ctx_session, ctx_cookies):
        try:
            self._unreal_get_free_resource(ctx=ctx_session, ctx_cookies=ctx_cookies)
        except AssertTimeout:
            logger.debug(
                ToolBox.runtime_report(
                    motive="QUIT", action_name=self.action_name, message="循环断言超时，任务退出。"
                )
            )
        except AuthException as error:
            logger.critical(
                ToolBox.runtime_report(
                    motive="SKIP", action_name=self.action_name, message=error.msg
                )
            )
            return False
