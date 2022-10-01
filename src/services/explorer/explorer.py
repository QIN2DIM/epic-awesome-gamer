# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import typing
from json.decoder import JSONDecodeError
from urllib.request import getproxies

import cloudscraper
from loguru import logger
from requests import RequestException

from services.utils.toolbox import ToolBox


class Explorer:
    """商城探索者 发现常驻免费游戏以及周免游戏"""

    # format:off
    URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    URL_PRODUCT_PAGE = "https://store.epicgames.com/zh-CN/p/"
    URL_ORDER_HISTORY = "https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory"
    # format:on

    cdn_image_urls = []

    def __init__(self):
        self.action_name = "Explorer"

        # 玩家在库资源总数（DLC/GAMES/UNREAL）
        self._orders_count = 0
        # 资源对象在库情况，普通促销商品以`UUID`命名，虚幻商店以`ue`作为key
        self._namespaces = set()
        # 周免游戲數據
        self._promotion_detailed = []

    @property
    def orders_count(self):
        return self._orders_count

    @property
    def namespaces(self):
        return self._namespaces

    @property
    def promotion_detailed(self):
        return self._promotion_detailed

    def get_promotions(
        self, ctx_cookies: typing.List[dict]
    ) -> typing.List[typing.Dict[str, typing.Union[str, bool]]]:
        """
        获取周免游戏数据

        <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
        <本周免费> promotion["promotions"]["promotionalOffers"]
        :param ctx_cookies:
        :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
        """
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36",
            "cookie": ToolBox.transfer_cookies(ctx_cookies),
        }
        params = {"locale": "zh-CN"}
        scraper = cloudscraper.create_scraper()
        response = scraper.get(self.URL_PROMOTIONS, params=params, headers=headers)

        try:
            data = response.json()
        except JSONDecodeError:
            pass
        else:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
            promotions = [e for e in elements if e.get("promotions")]
            # 获取商城促销数据&&获取<本周免费>的游戏对象
            for promotion in promotions:
                if promotion["promotions"]["promotionalOffers"]:
                    image_url = ""
                    try:
                        query = promotion["catalogNs"]["mappings"][0]["pageSlug"]
                        url = self.URL_PRODUCT_PAGE + query
                    except IndexError:
                        url = self.URL_PRODUCT_PAGE + promotion["productSlug"]
                    try:
                        image_url = promotion["keyImages"][-1]["url"]
                        self.cdn_image_urls.append(image_url)
                    except (KeyError, IndexError, AttributeError):
                        pass
                    # Implement Promotion Interface
                    self._promotion_detailed.append(
                        {
                            "url": url,
                            "title": promotion["title"],
                            "image_url": image_url,
                            "in_library": None,
                            "namespace": promotion["namespace"],
                        }
                    )

        return self._promotion_detailed

    def get_order_history(
        self,
        ctx_cookies: typing.List[dict],
        page: typing.Optional[str] = None,
        last_create_at: typing.Optional[str] = None,
    ) -> typing.Set[str]:
        """获取最近的订单纪录"""
        _kwargs = {
            "headers": {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.66 Safari/537.36 Edg/103.0.1264.44",
                "cookie": ToolBox.transfer_cookies(ctx_cookies),
            },
            "params": {"locale": "zh-CN", "page": page or "0", "latCreateAt": last_create_at or ""},
            "allow_redirects": False,
            "proxies": getproxies(),
        }
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(self.URL_ORDER_HISTORY, **_kwargs)
            if resp.status_code != 200:
                raise RequestException("Failed to get order history, cookie may have expired")
        except RequestException as err:
            logger.exception(err)
        else:
            try:
                data = json.loads(resp.text)
                orders: typing.List[dict] = data["orders"]
                self._orders_count = data["total"]
                for order in orders:
                    for item in order["items"]:
                        if order["orderStatus"] == "COMPLETED":
                            self._namespaces.add(item["namespace"])
            except (JSONDecodeError, KeyError) as err:
                logger.warning(err)
        return self._namespaces
