# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import typing

from playwright.sync_api import Page


class StoreExplorer:
    """游戏商店探索者 获取免费游戏数据以及促销信息"""

    URL_STORE_HOME = "https://store.epicgames.com/zh-CN/"
    URL_STORE_BROWSER = "https://store.epicgames.com/zh-CN/browse"
    URL_STORE_FREE_DLC = f"{URL_STORE_BROWSER}?sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&category=GameAddOn&count=40&start=0"
    URL_STORE_FREE_GAME = (
        f"{URL_STORE_BROWSER}?sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&count=40"
    )
    API_GRAPHQL = "https://store.epicgames.com/graphql"

    URL_EXPLORER_FREE_GAMES = (
        "https://store.epicgames.com/graphql?operationName=searchStoreQuery"
        '&variables={"allowCountries":"CN","category":"games/edition/base","comingSoon":false,"count":80,"country":"CN","effectiveDate":"[,2022-10-01T17:27:22.818Z]","freeGame":true,"keywords":"","locale":"zh-CN","sortBy":"releaseDate","sortDir":"DESC","start":0,"tag":"","withPrice":true}'
        '&extensions={"persistedQuery":{"version":1,"sha256Hash":"13a2b6787f1a20d05c75c54c78b1b8ac7c8bf4efc394edf7a5998fdf35d1adb0"}}'
    )

    def __init__(self, page: Page):
        self.action_name = "StoreExplorer"
        self.page = page

    def discovery_free_games(self, game_pool: GamePool):
        self.page.goto(self.URL_STORE_FREE_GAME, wait_until="domcontentloaded")
        self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        self.page.goto(self.URL_EXPLORER_FREE_GAMES, wait_until="domcontentloaded")
        data = json.loads(self.page.locator("//pre").text_content())

        # 一次请求获取当前商城可获取的所有免费游戏
        # 目前，游戏商城一页有40个游戏，大多数地区可领取的常驻免费游戏不超过80，即不超过两页
        search_store = data["data"]["Catalog"]["searchStore"]
        # 获取免费游戏总数
        self._total_free_games = search_store["paging"]["total"]
        # 编码数据对象
        elements: typing.List[dict] = search_store["elements"]
        url_prefix = "https://store.epicgames.com/zh-CN/p/"
        for element in elements:
            image_url = ""
            try:
                query = element["catalogNs"]["mappings"][0]["pageSlug"]
                url = url_prefix + query
            except IndexError:
                url = url_prefix + element["productSlug"]
            try:
                image_url = element["keyImages"][-1]["url"]
            except (KeyError, IndexError, AttributeError):
                pass
            # 实现 Promotion 数据对象接口
            detailed = {
                "title": element["title"],
                "url": url,
                "image_url": image_url,
                "in_library": None,
                "namespace": element["namespace"],
            }
            game_pool.put(**detailed)
