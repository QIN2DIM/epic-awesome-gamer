# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import time
from hashlib import sha256
from typing import List, Optional, Dict

import yaml
from loguru import logger
from selenium.common.exceptions import WebDriverException, InvalidCookieDomainException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from services.settings import DIR_EXPLORER
from services.utils import ToolBox
from .exceptions import DiscoveryTimeoutException, ProtocolOutdatedWarning


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
    URL_PROMOTIONS = (
        "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=zh-CN"
    )
    URL_PRODUCT_PAGE = "https://store.epicgames.com/zh-CN/p/"
    URL_ORDER_HISTORY = "https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory"

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

    def _discovery_free_games(self, ctx, ctx_cookies: List[dict], category: str = "game") -> None:
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
            WebDriverWait(ctx, 10, ignored_exceptions=(WebDriverException,)).until(
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
            WebDriverWait(ctx, 5, ignored_exceptions=(WebDriverException,)).until(
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
                            "name": name.split(",")[0].replace("\n", "").strip(),
                            "url": url.strip(),
                            "in_library": None,
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


class GameLibManager(EpicAwesomeExplorer):
    """游戏对象管理 缓存商城数据以及判断游戏在库状态"""

    def __init__(self, email: str):
        super().__init__()

        self.action_name = "GameLibManager"
        self.email = email
        self.auth_str = "explorer"

    def _z(self) -> str:
        return (
            sha256(f"{self.email[-3::-2]}{self.auth_str}".encode("utf-8")).hexdigest()
            if self.email
            else ""
        )

    def _check_protocol(self):
        """
        读取协议文件，检查协议头
        :except ProtocolOutdatedWarning: 缓存文件异常，请返回空数据
        :return:  stream
        """
        try:
            with open(self.path_free_games, "r", encoding="utf8") as file:
                ctx_protocol = yaml.safe_load(file)
        except FileNotFoundError as err:
            raise ProtocolOutdatedWarning from err
        else:
            if not ctx_protocol or not isinstance(ctx_protocol, dict):
                raise ProtocolOutdatedWarning
            return ctx_protocol

    @staticmethod
    def _update_status(game_objs, ctx_content=None, runtime: bool = False):
        """
        更新实体信息

        - case1 文件不存在 空文件 过时 协议。 跳过读取，初始化协议对象，创建并写入内容。
        - case2 缓存协议镜像，扩建实体，并逐条比对更新实体信息 加入新增内容，更新 ``in_library`` 状态

        :param game_objs: 详见 `Game Object`
        :param ctx_content: 实际上就是上一次保存的 game_objs
        :param runtime: 默认False，是否为运行时更新实例状态。
        一个显然的认知是，``IF runtime is False`` 为全量更新，应进行全库实例比对
        `` IF runtime is True `` 为局部更新，此时 new_objs 数量一般会远少于 memory_objs 的数量，
        应在比对后将 new_objs 的缺省实例补回。
        :type game_objs: List[Dict[str, str|bool]]
        :type ctx_content: List[Dict[str, str|bool]]
        :return:
        """
        if not ctx_content:
            return game_objs
        runtime = bool(runtime)

        new_objs_map = {game["url"]: game for game in game_objs}
        memory_objs_map = {c["url"]: c for c in ctx_content}
        new_content_objs = []

        # 对新内容迭代会自动丢弃过期的周免实例
        for flag in new_objs_map.keys():
            # 添加上一轮未发现的新游戏
            if not memory_objs_map.get(flag):
                new_content_objs.append(new_objs_map[flag])
            # 逐条对比 更新实体在库状态
            else:
                memory = memory_objs_map[flag]
                new_obj = new_objs_map[flag]
                if new_obj.get("in_library") is None:
                    new_obj["in_library"] = memory.get("in_library")
                # 添加更新在库状态后的实例
                new_content_objs.append(new_obj)

        # 将 new_objs 的缺省实例补回
        if runtime is True:
            for flag in memory_objs_map.keys():
                if not new_objs_map.get(flag):
                    new_content_objs.append(memory_objs_map[flag])

        return new_content_objs

    def save_game_objs(self, game_objs, category: str, runtime: Optional[bool] = None):
        """
        缓存免费商城数据
        :param runtime:
        :param game_objs:
        :param category:
        :type game_objs: List[Dict[str, str|bool]]
        :return:
        """
        if not game_objs:
            return

        try:
            ctx_protocol = self._check_protocol()
        except ProtocolOutdatedWarning:
            content = {self._z(): {category: game_objs}}
            with open(self.path_free_games, "w", encoding="utf8") as file:
                yaml.dump(content, file, allow_unicode=True)
            logger.success(
                ToolBox.runtime_report(
                    motive="SAVE",
                    action_name=self.action_name,
                    message="Cache Epic store information.",
                )
            )
        else:
            # 切换账号 键值补全
            if not ctx_protocol.get(self._z()):
                ctx_protocol[self._z()] = {}
            # 键值比对更新
            merged_content = self._update_status(
                game_objs=game_objs,
                ctx_content=ctx_protocol[self._z()].get(category),
                runtime=runtime,
            )
            ctx_protocol[self._z()].update({category: merged_content})
            # 缓存更新
            with open(self.path_free_games, "w", encoding="utf8") as file:
                yaml.dump(ctx_protocol, file, allow_unicode=True)
            logger.success(
                ToolBox.runtime_report(
                    motive="MERGE",
                    action_name=self.action_name,
                    message="Update Epic store information.",
                )
            )

    def load_game_objs(self, category: str, only_url: bool = None):
        """
        加载缓存在本地的免费游戏对象

        :param category:
        :param only_url:
        :return:
        """
        try:
            ctx_protocol = self._check_protocol()
        except ProtocolOutdatedWarning:
            return []
        else:
            ctx_content = ctx_protocol.get(self._z(), {}).get(category, [])
            if not ctx_content:
                return []
            if only_url is True:
                return [obj["url"] for obj in ctx_content]
            return ctx_content
