# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import csv
import json.decoder
from typing import List, Optional, Union, Dict, Any

import cloudscraper
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

    def save_game_objs(self, game_objs: List[Dict[str, str]]) -> None:
        """缓存免费商城数据"""
        if not game_objs:
            return

        with open(self.path_free_games, "w", encoding="utf8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["name", "url"])
            for game_obj in game_objs:
                cell = (game_obj["name"], game_obj["url"])
                writer.writerow(cell)

        logger.success(
            ToolBox.runtime_report(
                motive="SAVE",
                action_name=self.action_name,
                message="Cache free game information.",
            )
        )

    def load_game_objs(self, only_url: bool = True) -> Optional[List[str]]:
        """
        加载缓存在本地的免费游戏对象

        :param only_url:
        :return:
        """
        try:
            with open(self.path_free_games, "r", encoding="utf8") as file:
                data = list(csv.reader(file))
        except FileNotFoundError:
            return []
        else:
            if not data:
                return []
            if only_url:
                return [i[-1] for i in data[1:]]
            return data[1:]

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
            "Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62",
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

        assert_message = assert_obj[0].text
        response_obj = {"assert": assert_message, "warning": "", "status": None}

        # 🚧 跳过 `无法认领` 的日志信息
        if assert_message in ["已在游戏库中", "立即购买", "即将推出"]:
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
        self, ctx_cookies: Optional[List[dict]] = None, cover: bool = True
    ) -> Optional[List[str]]:
        """
        发现免费游戏。

        本周免费 + 常驻免费
        ________________________________________________________
        1. 此接口可以不传 cookie，免费游戏是公开可见的。
        2. 但如果要查看免费游戏的在库状态，需要传 COOKIE 区分用户。
            - 有些游戏不同地区的玩家不一定都能玩。这个限制和账户地区信息有关，和当前访问的（代理）IP 无关。
            - 请确保传入的 COOKIE 是有效的。
        :param cover:
        :param ctx_cookies: ToolBox.transfer_cookies(api.get_cookies())
        :return:
        """
        # 创建驱动上下文
        with get_ctx(silence=self.silence) as ctx:
            try:
                self._discovery_free_games(ctx=ctx, ctx_cookies=ctx_cookies)
            except DiscoveryTimeoutException:
                return self.discovery_free_games(ctx_cookies=None, cover=cover)

        # 提取游戏平台对象
        game_objs = self.game_objs.values()

        # 运行缓存持久化
        if cover:
            self.game_manager.save_game_objs(game_objs)

        # 返回链接
        return [game_obj.get("url") for game_obj in game_objs]

    def get_the_limited_free_game(
        self, ctx_cookies: Optional[List[dict]] = None
    ) -> Dict[str, Any]:
        """
        获取周免游戏

        :param ctx_cookies:
        :return:
        """

        def _update_limited_free_game_objs(element_: dict):
            free_game_objs[url] = element_["title"]
            free_game_objs["urls"].append(url)

        free_game_objs = {"urls": []}

        scraper = cloudscraper.create_scraper()
        response = scraper.get(self.URL_PROMOTIONS)

        try:
            data = response.json()
        except json.decoder.JSONDecodeError:
            pass
        else:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
            for element in elements:
                promotions = element.get("promotions")

                # 剔除掉过期的折扣实体
                if not promotions:
                    continue

                # 提取商品页slug
                url = self.URL_PRODUCT_PAGE + element["urlSlug"]

                # 健壮工程，预判数据类型的变更
                if not ctx_cookies:
                    # 获取实体的促销折扣值 discount_percentage
                    discount_setting = promotions["promotionalOffers"][0][
                        "promotionalOffers"
                    ][0]["discountSetting"]
                    discount_percentage = discount_setting["discountPercentage"]
                    if (
                        not isinstance(discount_percentage, str)
                        and not discount_percentage
                    ) or (
                        isinstance(discount_percentage, str)
                        and not float(discount_percentage)
                    ):
                        _update_limited_free_game_objs(element)
                else:
                    response = self.game_manager.is_my_game(
                        ctx_cookies=ctx_cookies, page_link=url
                    )
                    if (
                        not response["status"]
                        and response["assert"] != "AssertObjectNotFound"
                    ):
                        _update_limited_free_game_objs(element)

        return free_game_objs

    def get_the_absolute_free_game(
        self, ctx_cookies: Optional[List[dict]], _ctx_session=None
    ) -> Dict[str, Any]:
        """使用应力表达式萃取商品链接"""

        free_game_objs = {"urls": []}

        # 使用应力表达式萃取商品链接
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

        # 中断空对象的工作流
        if not pending_games:
            return free_game_objs

        # 任务批处理
        for url, title in pending_games.items():
            # 带入身份令牌判断周免游戏的在库状态
            response = self.game_manager.is_my_game(
                ctx_cookies=ctx_cookies, page_link=url
            )
            if not response["status"] and response["assert"] != "AssertObjectNotFound":
                # 将待认领的周免游戏送入任务队列
                free_game_objs[url] = title
                free_game_objs["urls"].append(url)

        return free_game_objs
