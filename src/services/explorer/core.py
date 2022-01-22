# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import csv
import os.path
import time
from typing import List, NoReturn

import cloudscraper
from bs4 import BeautifulSoup
from lxml import etree
from selenium.common.exceptions import (
    WebDriverException
)
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from services.settings import DIR_EXPLORER, logger
from services.utils import ToolBox, get_ctx


class AwesomeFreeGirl:
    def __init__(self, silence: bool = None):
        self.silence = True if silence is None else silence

        # 平台对象参数
        self.URL_FREE_GAMES = "https://www.epicgames.com/store/zh-CN/free-games"
        self.URL_STORE_PREFIX = "https://www.epicgames.com/store/zh-CN/browse?"
        self.URL_STORE_FREE = f"{self.URL_STORE_PREFIX}sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&count=40"
        self.URL_HOME = "https://www.epicgames.com"

        # 驱动参数
        self.action_name = "AwesomeFreeGirl"

        # 运行缓存
        self.runtime_workspace = None
        self.path_free_games = "free_games.csv"
        self.game_objs = {}  # {index0:{name:value url:value}, }

        # 初始化工作空间
        self._init_workspace()

    def _init_workspace(self) -> NoReturn:
        self.runtime_workspace = "." if not os.path.exists(DIR_EXPLORER) else DIR_EXPLORER
        self.path_free_games = os.path.join(self.runtime_workspace, self.path_free_games)

    def _discovery_free_games(self, ctx: Chrome, ctx_cookies: List[dict]):
        # 重载玩家令牌
        if ctx_cookies:
            ctx.get(self.URL_STORE_FREE)
            for cookie_dict in ctx_cookies:
                ctx.add_cookie(cookie_dict)

        # 获取免费游戏链接
        _url_store_free = self.URL_STORE_FREE
        while True:
            ctx.get(_url_store_free)
            time.sleep(1)
            WebDriverWait(ctx, 10, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//section[@data-testid='section-wrapper']"))
            )

            # 滑到底部
            action = ActionChains(ctx)
            action.send_keys(Keys.END)
            action.perform()

            # 判断异常跳转
            if "tierFree" not in ctx.current_url:
                break

            # 断言最后一页
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@data-component='PaginationItem']"))
            )
            page_switcher = ctx.find_elements(By.XPATH, "//a[@data-component='PaginationItem']")[-1]

            # 提取价值信息
            game_objs = ctx.find_elements(By.XPATH, "//a[@class='css-1jx3eyg']")
            for game_obj in game_objs:
                name = game_obj.get_attribute("aria-label")
                url = game_obj.get_attribute("href")
                self.game_objs.update(
                    {
                        self.game_objs.__len__(): {
                            "name": name.strip(),
                            "url": url.strip()
                        }
                    }
                )

            # 页面跳转判断
            page_end = page_switcher.get_attribute("href")
            if page_end in ctx.current_url:
                break

            # 更新跳转链接
            _url_store_free = page_end


class GameLibManager(AwesomeFreeGirl):
    def __init__(self):
        super(GameLibManager, self).__init__()

        self.action_name = "GameLibManager"

    def save_game_objs(self) -> NoReturn:
        if not self.game_objs:
            return False

        with open(self.path_free_games, "w", encoding='utf8', newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "url"])
            for game_obj in self.game_objs.values():
                cell = (game_obj["name"], game_obj["url"])
                writer.writerow(cell)

        logger.success(ToolBox.runtime_report(
            motive="SAVE",
            action_name=self.action_name,
            message="Cache free game information.",
        ))

    def load_game_objs(self, only_url: bool = True) -> list:
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

    def is_my_game(self, ctx_cookies: List[dict] or str, page_link: str):
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
    def __init__(self, silence: bool = None):
        super(Explorer, self).__init__(silence=silence)

        self.action_name = "Explorer"

        self.game_manager = GameLibManager()

    def discovery_free_games(self, ctx_cookies: List[dict] = None, save: bool = True) -> List[str]:
        """
        发现免费游戏。

        本周免费 + 常驻免费
        ________________________________________________________
        1. 此接口可以不传 cookie，免费游戏是公开可见的。
        2. 但如果要查看免费游戏的在库状态，需要传 COOKIE 区分用户。
            - 有些游戏不同地区的玩家不一定都能玩。这个限制和账户地区信息有关，和当前访问的（代理）IP 无关。
            - 请确保传入的 COOKIE 是有效的。
        :param save:
        :param ctx_cookies: ToolBox.transfer_cookies(api.get_cookies())
        :return:
        """
        # 创建驱动上下文
        with get_ctx(silence=self.silence) as ctx:
            self._discovery_free_games(ctx=ctx, ctx_cookies=ctx_cookies)

        # 运行缓存持久化
        if save:
            self.game_manager.save_game_objs()

        # 返回链接
        return [game_obj.get("url") for game_obj in self.game_objs.values()]
