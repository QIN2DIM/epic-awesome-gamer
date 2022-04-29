# -*- coding: utf-8 -*-
# Time       : 2022/4/6 19:52
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import time
from typing import List, Optional, Dict, Union

from bs4 import BeautifulSoup
from cloudscraper import create_scraper

from services.settings import logger
from services.utils import ToolBox
from .core import CookieManager, EpicAwesomeGamer
from .exceptions import AuthException, AssertTimeout, CookieExpired


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

    def __init__(self, silence: Optional[bool] = None):
        super().__init__()
        self.silence = True if silence is None else silence
        self.action_name = "UnrealClaimer"
        self.cookie_manager = CookieManager(auth_str=self.AUTH_STR_UNREAL)

    def get_claimer_response(self, ctx_cookies: List[dict]) -> List[Dict[str, Union[str, bool]]]:
        """领取任务后审查资源的在库状态"""
        headers = {"cookie": ToolBox.transfer_cookies(ctx_cookies)}
        scraper = create_scraper()
        response = scraper.get(self.URL_FREE_FOR_THE_MONTH, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        try:
            articles = soup.find("div", class_="asset-list-group").find_all("article")
        except AttributeError:
            logger.critical(
                ToolBox.runtime_report(
                    motive="CRASH",
                    action_name=self.action_name,
                    message="虚幻商店月供内容页元素改变或加载异常",
                    find_chains={"//div[@class='assert-list-group']", "//article"},
                )
            )
            return []
        else:
            if not articles:
                logger.critical(
                    ToolBox.runtime_report(
                        motive="MISS", action_name=self.action_name, message="虚幻商店月供内容或为空，请复查"
                    )
                )
                return []
            details = [
                {
                    "name": article.find("h3").text,
                    "url": f"{self.URL_UNREAL_HOME}{article.h3.a['href']}",
                    "in_library": "撰写评论" in article.text,
                }
                for article in articles
            ]

            return details

    def get_free_content(self, ctx, ctx_cookies):
        """获取虚幻商城的本月免费内容"""
        if not ctx_cookies:
            raise CookieExpired(self.assert_.COOKIE_EXPIRED)

        _loop_start = time.time()
        init = True
        while True:
            # [🚀] 重载身份令牌
            self._reset_page(
                ctx=ctx,
                page_link=self.URL_UNREAL_MONTH,
                ctx_cookies=ctx_cookies,
                auth_str=self.AUTH_STR_UNREAL,
            )

            # [🚀] 等待资源加载
            self.assert_.unreal_resource_load(ctx)

            # [🚀] 从虚幻商店购物车激活订单
            self.result = self.unreal_activate_payment(ctx, init=init)
            if self.result != self.assert_.GAME_PENDING:
                if self.result == self.assert_.ASSERT_OBJECT_EXCEPTION:
                    continue
                break

            # [🚀] 处理商品订单
            self.unreal_handle_payment(ctx)

            # [🚀] 更新上下文状态
            init = False
            self.assert_.timeout(_loop_start, self.loop_timeout)

    def claim_stabilizer(self, ctx_cookies: List[dict], ctx_session):
        try:
            self.get_free_content(ctx=ctx_session, ctx_cookies=ctx_cookies)
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
