# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json.decoder
from typing import List, Optional, Union, Dict

import cloudscraper
import yaml
from lxml import etree

from services.settings import logger
from services.utils import ToolBox, get_ctx
from .core import AwesomeFreeGirl
from .exceptions import DiscoveryTimeoutException


class GameLibManager(AwesomeFreeGirl):
    """游戏对象管理 缓存商城数据以及判断游戏在库状态"""

    def __init__(self):
        super().__init__()

        self.action_name = "GameLibManager"

    def save_game_objs(self, game_objs: List[Dict[str, str]], category: str) -> None:
        """缓存免费商城数据"""
        if not game_objs:
            return

        content = {game_obj["url"]: game_obj["name"] for game_obj in game_objs}
        with open(self.path_free_games, "w", encoding="utf8", newline="") as file:
            yaml.dump({category: content}, file, allow_unicode=True)

        logger.success(
            ToolBox.runtime_report(
                motive="SAVE",
                action_name=self.action_name,
                message="Cache Epic store information.",
            )
        )

    def load_game_objs(self, category: str, only_url: bool = True) -> Optional[List[str]]:
        """
        加载缓存在本地的免费游戏对象

        :param category:
        :param only_url:
        :return:
        """
        try:
            with open(self.path_free_games, "r", encoding="utf8") as file:
                content: Dict[str, Dict[str, str]] = yaml.load(file, Loader=yaml.Loader)
        except FileNotFoundError:
            return []
        else:
            if not content or not isinstance(content, dict) or not content.get(category):
                return []
            if only_url:
                return list(content[category].keys())
            return list(content[category].items())

    def is_my_game(
        self, ctx_cookies: Union[List[dict], str], page_link: str
    ) -> Optional[dict]:
        """
        判断游戏在库状态

        :param ctx_cookies:
        :param page_link:
        :return:
            None 异常状态
            True 跳过任务
            False 继续任务
        """
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36",
            "cookie": ctx_cookies
            if isinstance(ctx_cookies, str)
            else ToolBox.transfer_cookies(ctx_cookies),
        }
        scraper = cloudscraper.create_scraper()
        response = scraper.get(page_link, headers=headers)
        tree = etree.HTML(response.content)
        assert_obj = tree.xpath(
            "//span[@data-component='PurchaseCTA']//span[@data-component='Message']"
        )

        # 🚧 异常状态
        if not assert_obj:
            logger.debug(
                ToolBox.runtime_report(
                    motive="IGNORE",
                    action_name=self.action_name,
                    message="忽略尚未发布的游戏对象",
                    url=page_link,
                )
            )
            return {"assert": "AssertObjectNotFound", "status": None}

        # [购买|获取|已在库中|即将推出]
        assert_message = assert_obj[0].text
        response_obj = {"assert": assert_message, "warning": "", "status": None}

        # 🚧 跳过 `无法认领` 的日志信息
        if assert_message in ["已在游戏库中", "已在库中", "立即购买", "购买", "即将推出"]:
            response_obj["status"] = True
        # 🚧 惰性加载，前置节点不处理动态加载元素
        elif assert_message in ["正在载入"]:
            response_obj["status"] = False
        # 🍟 未领取的免费游戏
        elif assert_message in ["获取"]:
            warning_obj = tree.xpath("//h1[@class='css-1gty6cv']//span")
            # 出现遮挡警告
            if warning_obj:
                warning_message = warning_obj[0].text
                response_obj["warning"] = warning_message
                # 成人内容可获取
                if "成人内容" in warning_message:
                    response_obj["status"] = False
                else:
                    logger.warning(
                        ToolBox.runtime_report(
                            motive="SKIP",
                            action_name=self.action_name,
                            message=warning_message,
                            url=page_link,
                        )
                    )
                    response_obj["status"] = None
            # 继续任务
            else:
                response_obj["status"] = False

        return response_obj


class Explorer(AwesomeFreeGirl):
    """商城探索者 发现常驻免费游戏以及周免游戏"""

    def __init__(self, silence: Optional[bool] = None):
        super().__init__(silence=silence)

        self.action_name = "Explorer"

        self.game_manager = GameLibManager()

    def discovery_free_games(
        self,
        ctx_cookies: Optional[List[dict]] = None,
        cover: bool = True,
        category: str = "game",
    ) -> Optional[List[str]]:
        """
        发现免费游戏。

        本周免费 + 常驻免费
        ________________________________________________________
        1. 此接口可以不传 cookie，免费游戏是公开可见的。
        2. 但如果要查看免费游戏的在库状态，需要传 COOKIE 区分用户。
            - 有些游戏不同地区的玩家不一定都能玩。这个限制和账户地区信息有关，和当前访问的（代理）IP 无关。
            - 请确保传入的 COOKIE 是有效的。
        :param category: 搜索模式 self.category.keys()
        :param cover:
        :param ctx_cookies: ToolBox.transfer_cookies(api.get_cookies())
        :return:
        """
        category = (
            "game" if category not in list(self.category_details.keys()) else category
        )

        # 创建驱动上下文
        with get_ctx(silence=self.silence) as ctx:
            try:
                self._discovery_free_games(
                    ctx=ctx, ctx_cookies=ctx_cookies, category=category
                )
            except DiscoveryTimeoutException:
                return self.discovery_free_games(
                    ctx_cookies=None, cover=cover, category=category
                )

        # 提取游戏平台对象
        game_objs = self.game_objs.values()

        # 运行缓存持久化
        if cover:
            self.game_manager.save_game_objs(game_objs, category=category)

        # 返回链接
        return [game_obj.get("url") for game_obj in game_objs]

    def get_promotions(self, ctx_cookies: List[dict]) -> Dict[str, Union[List[str], str]]:
        """
        获取周免游戏数据

        <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
        <本周免费> promotion["promotions"]["promotionalOffers"]
        :param ctx_cookies:
        :return: {"urls": [], "pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
        """
        free_game_objs = {"urls": []}
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36",
            "cookie": ToolBox.transfer_cookies(ctx_cookies),
        }
        scraper = cloudscraper.create_scraper()
        response = scraper.get(self.URL_PROMOTIONS, headers=headers)

        try:
            data = response.json()
        except json.decoder.JSONDecodeError:
            pass
        else:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
            promotions = [e for e in elements if e.get("promotions")]

            # 获取商城促销数据
            for promotion in promotions:
                # 获取<本周免费>的游戏对象
                if promotion["promotions"]["promotionalOffers"]:
                    url = (
                        self.URL_PRODUCT_PAGE
                        + promotion["catalogNs"]["mappings"][0]["pageSlug"]
                    )
                    free_game_objs["urls"].append(url)
                    free_game_objs[url] = promotion["title"]

        return free_game_objs

    def get_promotions_by_stress_expressions(
        self, _ctx_session=None
    ) -> Dict[str, Union[List[str], str]]:
        """使用应力表达式萃取商品链接"""
        free_game_objs = {"urls": []}
        if _ctx_session:
            critical_memory = _ctx_session.current_window_handle
            try:
                _ctx_session.switch_to.new_window("tab")
                pending_games: Dict[str, str] = self.stress_expressions(ctx=_ctx_session)
            finally:
                _ctx_session.switch_to.window(critical_memory)
        else:
            with get_ctx(silence=self.silence) as ctx:
                pending_games: Dict[str, str] = self.stress_expressions(ctx=ctx)

        if pending_games:
            for url, title in pending_games.items():
                free_game_objs[url] = title
                free_game_objs["urls"].append(url)
        return free_game_objs
