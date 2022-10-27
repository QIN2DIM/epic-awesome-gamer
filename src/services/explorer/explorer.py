# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import time
import typing
from contextlib import suppress
from json.decoder import JSONDecodeError
from os.path import isfile, getmtime
from urllib.request import getproxies

import requests
import yaml
from loguru import logger
from playwright.sync_api import Page
from requests import RequestException

from services.utils.toolbox import ToolBox
from .core import GamePool, new_store_explorer


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

    def get_free_now(self, page: Page):
        """获取准确的周免游戏数据"""
        promotions = self.get_promotions()
        page.goto("https://store.epicgames.com/zh-CN/", wait_until="domcontentloaded")
        free_games = page.locator("//a[contains(@aria-label,'现在免费')]")
        free_games.last.wait_for()
        hrefs = {
            "https://store.epicgames.com" + free_games.nth(i).get_attribute("href")
            for i in range(free_games.count())
        }
        promotions = [promotion for promotion in promotions if promotion["url"] in hrefs]
        return promotions

    def get_promotions(self) -> typing.List[typing.Dict[str, typing.Union[str, bool]]]:
        """
        获取周免游戏数据

        <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
        <本周免费> promotion["promotions"]["promotionalOffers"]
        :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
        """
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36"
        }
        params = {"locale": "zh-CN"}
        response = requests.get(self.URL_PROMOTIONS, params=params, headers=headers)

        try:
            data = response.json()
        except JSONDecodeError:
            pass
        else:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
            promotions = [e for e in elements if e.get("promotions")]
            # 获取商城促销数据&&获取<本周免费>的游戏对象
            for promotion in promotions:
                if offer := promotion["promotions"]["promotionalOffers"]:
                    # 去除打折了但只打一点点的商品
                    with suppress(KeyError, IndexError):
                        offer = offer[0]["promotionalOffers"][0]
                        if offer["discountSetting"]["discountPercentage"]:
                            continue
                    try:
                        query = promotion["catalogNs"]["mappings"][0]["pageSlug"]
                        url = self.URL_PRODUCT_PAGE + query
                    except IndexError:
                        url = self.URL_PRODUCT_PAGE + promotion["productSlug"]
                    with suppress(KeyError, IndexError, AttributeError):
                        image_url = promotion["keyImages"][-1]["url"]
                        self.cdn_image_urls.append(image_url)
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
            resp = requests.get(self.URL_ORDER_HISTORY, **_kwargs)
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


class PermissionsHistory:
    def __init__(
        self,
        dir_hook: str,
        ctx_cookies,
        outdated_interval_order_history: typing.Optional[int] = 86400,
        outdated_interval_ctx_store: typing.Optional[int] = 259200,
        path_ctx_store: typing.Optional[str] = "ctx_store.yaml",
        path_order_history: typing.Optional[str] = "order_history.yaml",
    ):
        self.dir_hook = dir_hook
        self.ctx_cookies = ctx_cookies

        self.game_pool = GamePool()
        self.total_free_games = 0
        self.path_ctx_store = path_ctx_store
        self.path_order_history = path_order_history
        self.outdated_interval_order_history = outdated_interval_order_history
        self.outdated_interval_ctx_store = outdated_interval_ctx_store
        self.namespaces: typing.Set[str] = set()
        self.key_images: typing.List[str] = []

    def load_memory(self):
        memory2lifecycle = {
            self.path_order_history: self.outdated_interval_order_history,
            self.path_ctx_store: self.outdated_interval_ctx_store,
        }
        for path_memory, lifecycle in memory2lifecycle.items():
            if not isfile(path_memory):
                continue
            modify_interval = time.time() - getmtime(path_memory)
            remain_interval = lifecycle - modify_interval
            if modify_interval >= lifecycle:
                continue
            with open(path_memory, "r", encoding="utf8") as file:
                data = yaml.safe_load(file)
            with suppress(TypeError, AttributeError):
                if path_memory == self.path_order_history:
                    logger.info(f"加载历史订单数据 本地缓存{int(remain_interval / 3600)}小时有效")
                    self.namespaces = data or self.namespaces
                elif path_memory == self.path_ctx_store:
                    logger.info(f"加载历史商城数据 本地缓存{int(remain_interval / 3600)}小时有效")
                    for game in data["_games"]:
                        self.game_pool.put(**game)
                        self.total_free_games += 1

    def get_ctx_store(self, page: Page):
        # 获取商城免费游戏数据
        if self.game_pool.empty():
            logger.info("初始化商城数据")
            store_explorer = new_store_explorer(page)
            store_explorer.discovery_free_games(game_pool=self.game_pool)
            self.total_free_games = store_explorer.total_free_games
            # 缓存商城免费游戏数据
            self.save_ctx_store()

    def get_oder_history(self, ctx_cookies=None):
        # 获取玩家历史订单数据
        if not self.namespaces:
            logger.info("初始化订单数据")
            ctx_cookies = ctx_cookies or self.ctx_cookies
            explorer = Explorer()
            if resp := explorer.get_order_history(ctx_cookies):
                pages = int((explorer.orders_count * 1.2 - len(resp)) / 10) + 1
                for page in range(1, pages + 1):
                    explorer.get_order_history(ctx_cookies, page=str(page))
                self.namespaces = explorer.namespaces
            # 緩存歷史訂單數據
            self.save_order_history()

    def save_order_history(self):
        with open(self.path_order_history, "w", encoding="utf8") as file:
            yaml.safe_dump(self.namespaces, file)

    def save_ctx_store(self):
        with open(self.path_ctx_store, "w", encoding="utf8") as file:
            yaml.safe_dump(self.game_pool.to_dict(), file)
