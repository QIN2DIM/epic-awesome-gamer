# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import os.path
import time
from hashlib import sha256
from typing import List, Optional, Union, Dict

import cloudscraper
import requests.exceptions
import yaml
from lxml import etree  # skipcq: BAN-B410 - Ignore credible sources
from selenium.common.exceptions import WebDriverException, InvalidCookieDomainException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from services.settings import DIR_EXPLORER, EPIC_EMAIL
from services.settings import logger
from services.utils import ToolBox, ChallengerContext, StandardContext
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
    URL_ORDER_HISTORY = (
        "https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory?locale=zh-CN"
    )

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
        ctx: Union[ChallengerContext, StandardContext],
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

    def stress_expressions(self, ctx: Union[ChallengerContext, StandardContext]) -> Dict[str, str]:
        """应力表达式的主要实现"""
        logger.debug(
            ToolBox.runtime_report(
                motive="DISCOVERY", action_name=self.action_name, message="📡 使用应力表达式搜索周免游戏..."
            )
        )

        # 访问链接 游戏名称
        pending_games = {}

        for i in range(2):
            try:
                ctx.get(self.URL_STORE_HOME)
                time.sleep(3)

                # 定位周免游戏的绝对位置
                WebDriverWait(ctx, 45, ignored_exceptions=(WebDriverException,)).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(string(),'当前免费')]"))
                )

                # 周免游戏基本信息
                stress_operator = ctx.find_elements(By.XPATH, "//a[contains(string(),'当前免费')]")
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
        self.email = EPIC_EMAIL
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

    @staticmethod
    def is_my_game(ctx_cookies, page_link: str, pre_assert_content: bytes = None) -> Optional[dict]:
        """
        判断游戏在库状态

        :param pre_assert_content: 前置协同响应流，将耗时的网络请求操作前置，
          封装成协程任务，而仅将此函数用于解析上游模块的静态返回值。
        :param ctx_cookies:
        :param page_link:
        :type ctx_cookies: List[dict]|str
        :return:
            None 异常状态
            True 跳过任务
            False 继续任务
            仅当返回值为 False 时可以继续任务，并可以进一步筛选掉 AjaxLoadingReject 目标。
        """

        def response_wrapper(new_params: dict):
            resp_ = {"assert": "", "status": None, "warning": ""}
            resp_.update(new_params)
            return resp_

        # 模式匹配 --> 上下文呈递|重新握手
        if pre_assert_content is None:
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36",
                "cookie": ctx_cookies
                if isinstance(ctx_cookies, str)
                else ToolBox.transfer_cookies(ctx_cookies),
            }
            scraper = cloudscraper.create_scraper()
            response = scraper.get(page_link, headers=headers)
            content = response.content
        else:
            content = pre_assert_content

        # 清洗页面的促销信息
        tree = etree.HTML(content)
        assert_obj = tree.xpath(
            "//span[@data-component='PurchaseCTA']//span[@data-component='Message']"
        )

        # 模式匹配 --> 向下游呈递资源对象的状态
        # 1. 剔除已在库的、付费的、未推出的资源；
        # 2. 剔除被限制的免费资源；
        # 3. 呈递待领取的免费资源；

        # 🚧 异常状态 忽略尚未发布的游戏对象
        if not assert_obj:
            return response_wrapper({"assert": "AssertObjectNotFound", "status": None})
        assert_message = assert_obj[0].text

        # 🚧 跳过 `无法认领` 的日志信息
        if assert_message in ["已在游戏库中", "已在库中", "立即购买", "购买", "即将推出"]:
            return response_wrapper({"assert": assert_message, "status": True})

        # 🚧 惰性加载，前置节点不处理动态加载元素
        if assert_message in ["正在载入"]:
            return response_wrapper({"assert": "AjaxLoadingReject", "status": False})

        # 🍟 未领取的免费游戏
        if assert_message in ["获取"]:
            # 無遮挡警告 繼續任務
            warning_obj = tree.xpath("//h1[@class='css-1gty6cv']//span")
            if not warning_obj:
                return response_wrapper({"assert": assert_message, "status": False})

            # 成人内容可获取
            warning_message = warning_obj[0].text
            if warning_message in ["成人内容"]:
                return response_wrapper(
                    {"assert": assert_message, "warning": warning_message, "status": False}
                )

            # 地区限制無法獲取
            return response_wrapper(
                {"assert": assert_message, "warning": warning_message, "status": None}
            )

    def get_order_history(self, ctx_cookies) -> Optional[Dict[str, bool]]:
        """
        获取订单历史信息
        :param ctx_cookies:
        :return: container:Dict[str, bool] = {"game_name_1": boolean, ...}
        """
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/103.0.5060.66 Safari/537.36 Edg/103.0.1264.44",
            "cookie": ctx_cookies
            if isinstance(ctx_cookies, str)
            else ToolBox.transfer_cookies(ctx_cookies),
        }
        # 订单项目
        container = {}

        # 解析订单数据
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(self.URL_ORDER_HISTORY, headers=headers)
        except requests.exceptions.RequestException as err:
            logger.exception(err)
        else:
            try:
                data = json.loads(resp.text)
                orders: List[dict] = data["orders"]
                for order in orders:
                    items: List[dict] = order["items"]
                    for item in items:
                        container[item["description"]] = bool(order["orderStatus"] == "COMPLETED")
            except (json.decoder.JSONDecodeError, KeyError) as err:
                logger.exception(err)
        finally:
            return container


class _Game:
    """基础游戏对象"""

    # 游戏名称
    name: str = "《堡垒之夜》"
    # 商城访问链接
    url: str = "https://store.epicgames.com/zh-CN/p/fortnite"
    # 在库情况 True在库 False不在 None不到啊(初始化状态)
    in_library: bool = None


class _Dlc:
    """游戏附加内容对象"""

    # 附加内容名称
    name: str = "《消逝的光芒》-《求生之路 2》Weapon Pack"
    # 商城访问链接
    url: str = "https://store.epicgames.com/zh-CN/p/dying-light--left-4-dead-2-weapon-pack"
    # 在库情况 True在库 False不在 None不到啊(初始化状态)
    in_library: bool = None


class _Report:
    """消息推送|资源封装对象"""

    # 资源名称
    name: str = ""
    # 资源链接
    url: str = ""
    # 执行结果
    status: str = ""
