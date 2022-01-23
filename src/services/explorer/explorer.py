# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import csv
from typing import List, Optional, Union, Dict

import cloudscraper
from bs4 import BeautifulSoup
from lxml import etree

from services.settings import logger
from services.utils import (
    ToolBox,
    get_ctx
)
from .core import AwesomeFreeGirl
from .exceptions import DiscoveryTimeoutException


class GameLibManager(AwesomeFreeGirl):
    def __init__(self):
        super(GameLibManager, self).__init__()

        self.action_name = "GameLibManager"

    def save_game_objs(self, game_objs: List[Dict[str, str]]) -> None:
        if not game_objs:
            return

        with open(self.path_free_games, "w", encoding='utf8', newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "url"])
            for name, url in game_objs:
                writer.writerow((name, url))

        logger.success(ToolBox.runtime_report(
            motive="SAVE",
            action_name=self.action_name,
            message="Cache free game information.",
        ))

    def load_game_objs(self, only_url: bool = True) -> Optional[List[str]]:
        """
        加载缓存在本地的免费游戏对象

        :param only_url:
        :return:
        """
        try:
            with open(self.path_free_games, "r", encoding="utf8") as f:
                data = list(csv.reader(f))
        except FileNotFoundError:
            return []
        else:
            if not data:
                return []
            if only_url:
                return [i[-1] for i in data[1:]]
            return data[1:]

    def is_my_game(self, ctx_cookies: Union[List[dict], str], page_link: str) -> Optional[bool]:
        """

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
            "cookie": ctx_cookies if type(ctx_cookies) == str else ToolBox.transfer_cookies(ctx_cookies)
        }
        scraper = cloudscraper.create_scraper()
        response = scraper.get(page_link, headers=headers)
        tree = etree.HTML(response.content)
        assert_message = tree.xpath("//span[@data-component='PurchaseCTA']//span[@data-component='Message']")

        # 异常状态
        if not assert_message:
            logger.warning(ToolBox.runtime_report(
                motive="SKIP",
                action_name=self.action_name,
                message=BeautifulSoup(response.text, "html.parser").text,
                url=page_link
            ))
            return None
        # 跳过任务
        if assert_message[0].text in ["已在游戏库中", "立即购买"]:
            return True
        # 惰性加载
        if assert_message[0].text in ["正在载入", ]:
            return False
        # 未领取的免费游戏
        if assert_message[0].text in ["获取", ]:
            warning_obj = tree.xpath("//h1[@class='css-1gty6cv']//span")
            # 出现遮挡警告
            if warning_obj:
                logger.warning(ToolBox.runtime_report(
                    motive="SKIP",
                    action_name=self.action_name,
                    message=warning_obj[0].text,
                    url=page_link
                ))
                return None
            # 继续任务
            return False


class Explorer(AwesomeFreeGirl):
    def __init__(self, silence: Optional[bool] = None):
        super(Explorer, self).__init__(silence=silence)

        self.action_name = "Explorer"

        self.game_manager = GameLibManager()

    def discovery_free_games(self, ctx_cookies: Optional[List[dict]] = None, cover: bool = True) -> Optional[List[str]]:
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
