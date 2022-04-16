# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import time
from typing import ContextManager

# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import List, Optional, Union, Dict

import cloudscraper
import yaml
from lxml import etree
from selenium.common.exceptions import WebDriverException, InvalidCookieDomainException
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from services.settings import DIR_EXPLORER
from services.settings import logger
from services.utils import ToolBox
from .exceptions import DiscoveryTimeoutException


class EpicAwesomeExplorer:
    """游戏商店探索者 获取免费游戏数据以及促销信息"""

    # 平台对象参数
    URL_STORE_HOME = "https://store.epicgames.com/zh-CN/"
    URL_FREE_GAMES = "https://store.epicgames.com/zh-CN/free-games"
    URL_STORE_PREFIX = "https://store.epicgames.com/zh-CN/browse?"
    URL_STORE_FREE_GAME = (
        f"{URL_STORE_PREFIX}sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&count=40"
    )
    URL_STORE_FREE_DLC = f"{URL_STORE_PREFIX}sortBy=releaseDate&sortDir=DESC&priceTier=tierFree&category=GameAddOn&count=40&start=0"  # noqa
    URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=zh-CN"
    URL_PRODUCT_PAGE = "https://store.epicgames.com/zh-CN/p/"

    def __init__(self, silence: bool = None):
        self.silence = True if silence is None else silence

        # 驱动参数
        self.action_name = "AwesomeFreeGirl"

        # 运行缓存
        self.runtime_workspace = None
        self.path_free_games = "ctx_store.yaml"
        self.game_objs = {}  # {index0:{name:value url:value}, }
        self.category_details = {
            "game": {"url": self.URL_STORE_FREE_GAME, "flag": "免费游戏"},
            "dlc": {"url": self.URL_STORE_FREE_DLC, "flag": "免费附加内容"},
        }

        # 初始化工作空间
        self._init_workspace()

    def _init_workspace(self) -> None:
        """初始化工作目录 缓存游戏商店数据"""
        self.runtime_workspace = "." if not os.path.exists(DIR_EXPLORER) else DIR_EXPLORER
        self.path_free_games = os.path.join(self.runtime_workspace, self.path_free_games)

    def _discovery_free_games(
        self,
        ctx: Union[ContextManager, Chrome],
        ctx_cookies: List[dict],
        category: str = "game",
    ) -> None:
        """发现玩家所属地区可视的常驻免费游戏数据"""
        url = self.category_details[category]["url"]
        flag = self.category_details[category]["flag"]

        # 重载玩家令牌
        if ctx_cookies:
            ctx.get(self.URL_STORE_FREE_GAME)
            for cookie_dict in ctx_cookies:
                try:
                    ctx.add_cookie(cookie_dict)
                except InvalidCookieDomainException:
                    pass

        _mode = "（深度搜索）" if ctx_cookies else "（广度搜索）"
        logger.debug(
            ToolBox.runtime_report(
                motive="DISCOVERY",
                action_name=self.action_name,
                message=f"📡 正在为玩家搜集{flag}{_mode}...",
            )
        )

        # 获取免费游戏链接
        _start = time.time()
        _url_store_free = url
        while True:
            ctx.get(_url_store_free)
            time.sleep(1)
            WebDriverWait(ctx, 10, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//section[@data-testid='section-wrapper']")
                )
            )

            # 滑到底部
            action = ActionChains(ctx)
            action.send_keys(Keys.END)
            action.perform()

            # 判断异常跳转
            if "tierFree" not in ctx.current_url:
                break
            if time.time() - _start > 80:
                raise DiscoveryTimeoutException(f"获取{flag}链接超时")

            # 断言最后一页
            WebDriverWait(ctx, 5, ignored_exceptions=WebDriverException).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[@data-component='PaginationItem']")
                )
            )
            page_switcher = ctx.find_elements(
                By.XPATH, "//a[@data-component='PaginationItem']"
            )[-1]

            # 提取价值信息
            game_objs = ctx.find_elements(By.XPATH, "//a[@class='css-1jx3eyg']")
            for game_obj in game_objs:
                name = game_obj.get_attribute("aria-label")
                url = game_obj.get_attribute("href")
                self.game_objs.update(
                    {
                        self.game_objs.__len__(): {
                            "name": name.split(",")[0].replace("\n", "").strip(),
                            "url": url.strip(),
                        }
                    }
                )

            # 页面跳转判断
            page_end = page_switcher.get_attribute("href")
            if page_end in ctx.current_url:
                break

            # 更新跳转链接
            _url_store_free = page_end

        logger.success(
            ToolBox.runtime_report(
                motive="DISCOVERY",
                action_name=self.action_name,
                message=f"{flag}搜集完毕",
                qsize=len(self.game_objs),
            )
        )

    def stress_expressions(self, ctx: Union[ContextManager, Chrome]) -> Dict[str, str]:
        """
        应力表达式的主要实现

        :param ctx: 浏览器驱动上下文
        :return: 不需要 quit()
        """
        logger.debug(
            ToolBox.runtime_report(
                motive="DISCOVERY",
                action_name=self.action_name,
                message="📡 使用应力表达式搜索周免游戏...",
            )
        )

        # 访问链接 游戏名称
        pending_games = {}

        for i in range(2):
            try:
                ctx.get(self.URL_STORE_HOME)
                time.sleep(3)

                # 定位周免游戏的绝对位置
                WebDriverWait(ctx, 45, ignored_exceptions=WebDriverException).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[contains(string(),'当前免费')]")
                    )
                )

                # 周免游戏基本信息
                stress_operator = ctx.find_elements(
                    By.XPATH, "//a[contains(string(),'当前免费')]"
                )
                title_seq = ctx.find_elements(
                    By.XPATH,
                    "//a[contains(string(),'当前免费')]//span[@data-testid='offer-title-info-title']",
                )

                # 重组周免游戏信息
                for index, _ in enumerate(stress_operator):
                    href = stress_operator[index].get_attribute("href")
                    try:
                        pending_games[href] = f"{title_seq[index].text}".strip()
                    except AttributeError as err:
                        if i == 0:
                            raise AttributeError from err
                        pending_games[href] = "null"

                break
            except (WebDriverException, AttributeError):
                continue

        return pending_games


class GameLibManager(EpicAwesomeExplorer):
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
