# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import os.path
from dataclasses import dataclass
from queue import Queue
from typing import Literal, List

from loguru import logger
from playwright.sync_api import BrowserContext

from services.bricklayer.game import GameClaimer, empower_games_claimer
from services.bricklayer.unreal import UnrealClaimer
from services.explorer.explorer import Explorer, PermissionsHistory
from settings import project
from utils.pusher import MessageBody, MessageQueue


@dataclass
class Promotion:
    """实现促销商品的对象接口，构建来自游戏商城和虚幻商城的促销实体"""

    url: str
    title: str
    image_url: str = ""
    in_library: bool = None
    namespace: str = ""  # Only for games-claimer

    def __post_init__(self):
        """在实例化后执行，对传入的初始化值进行处理"""
        self.title = self.title.replace("《", "").replace("》", "").strip()


@dataclass
class Promotions:
    promotion_sequence: List[Promotion] = None

    def __post_init__(self):
        self.promotion_sequence = self.promotion_sequence or []

    def new_promotion(self, **kwargs):
        self.promotion_sequence.append(Promotion(**kwargs))


# Scheduler 核心核心邏輯：
# 1. 运行前检查 cookie 有效性
#   尝试初始化 cookie，读入 cookie
# 2. 对于 epic, 可以直接发起携带 cookie 的 request 请求
#   - 查询用户游戏库
# 3. 对于 epic，可以直接发起 request 请求查询当周促销游戏


class BaseInstance:
    """Atomic Scheduler"""

    def __init__(self):
        # 服务注册
        self.bricklayer = GameClaimer()
        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.promotions = Promotions()
        self.task_queue_pending = Queue()
        self.task_sequence_worker = []
        # 消息队列 按序缓存认领任务的执行状态
        self.message_queue = MessageQueue()
        self.inline_docker: List[MessageBody] = []
        # 资源在库状态简写
        self.in_library = self.bricklayer.assert_util.GAME_OK
        self.claimed = self.bricklayer.assert_util.GAME_CLAIM

        self._ctx_cookies = None

    def _push_pending_message(self, result, promotion: Promotion):
        element = MessageBody(url=promotion.url, title=promotion.title, result=result, dlc=False)
        self.message_queue.put(element)

    def is_pending(self) -> bool | None:
        """是否可发起驱动任务 True:执行 False/None:结束"""
        return self.task_sequence_worker and self._ctx_cookies


class GameClaimerInstance(BaseInstance):
    """单步子任务 认领周免游戏"""

    def __init__(self):
        super(GameClaimerInstance, self).__init__()
        self.explorer = Explorer()

        # Pending order history
        self.dir_hook = project.claim_history_dir
        suffix = self.bricklayer.cookie_manager.hash
        self.path_ctx_store = os.path.join(self.dir_hook, f"ctx_store_{suffix}.yaml")
        self.path_order_history = os.path.join(self.dir_hook, f"order_history_{suffix}.yaml")
        self.ph = PermissionsHistory(
            dir_hook=self.dir_hook,
            ctx_cookies=self._ctx_cookies,
            path_ctx_store=self.path_ctx_store,
            path_order_history=self.path_order_history,
            outdated_interval_order_history=432000,
        )

    def get_promotions(self) -> List[Promotion]:
        """获取游戏促销信息"""
        promotions = self.explorer.get_promotions()
        for promotion in promotions:
            self.promotions.new_promotion(**promotion)
        return self.promotions.promotion_sequence

    def preload(self):
        self._ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()
        if not self._ctx_cookies:
            return self.get_promotions()
        # 获取历史订单数据
        self.ph.load_memory()
        self.ph.get_oder_history(ctx_cookies=self._ctx_cookies)
        order_history = self.ph.namespaces
        # 获取周免促销数据
        promotions = self.get_promotions()
        # 标记促销实体的在库状态
        _offload = set()
        for promotion in promotions:
            if promotion.url in _offload:
                continue
            _offload.add(promotion.url)
            if in_library := promotion.namespace in order_history:
                self._push_pending_message(result=self.in_library, promotion=promotion)
                logger.debug(f"{promotion.title} - state=已在库中 link={promotion.url}")
            else:
                self.task_sequence_worker.append(promotion)
                logger.debug(f"{promotion.title} - state=待认领 link={promotion.url}")
            promotion.in_library = in_library
        return self.task_sequence_worker

    def just_do_it(self):
        def run(context: BrowserContext):
            context.storage_state(path=self.bricklayer.cookie_manager.path_ctx_cookies)
            promotions = self.preload()
            page = context.new_page()
            for promotion in promotions:
                self.bricklayer.promotion_url2title[promotion.url] = promotion.title
                result = empower_games_claimer(self.bricklayer, promotion.url, page, pattern="get")
                self._push_pending_message(result=result, promotion=promotion)

        tarnished.execute(sequence=[self.bricklayer.cookie_manager.refresh_ctx_cookies, run])


class UnrealClaimerInstance(BaseInstance):
    """虚幻商城月供砖家"""

    def __init__(self):
        super().__init__()
        self.bricklayer = UnrealClaimer()

    def get_promotions(self) -> List[Promotion]:
        promotions = self.bricklayer.get_promotions(self._ctx_cookies)
        for promotion in promotions:
            self.promotions.new_promotion(**promotion)
        return self.promotions.promotion_sequence

    def preload(self):
        _offload = set()
        for promotion in self.get_promotions():
            if promotion.url in _offload:
                continue
            _offload.add(promotion.url)
            if promotion.in_library:
                self._push_pending_message(result=self.in_library, promotion=promotion)
                logger.debug(f"{promotion.title} - state=已在库中 link={promotion.url}")
            else:
                self.task_sequence_worker.append(promotion)
                logger.debug(f" {promotion.title}] - state=待认领 link={promotion.url}")

    def just_do_it(self):
        def run(context: BrowserContext):
            result = self.bricklayer.get_free_content(page=context.new_page())
            for promotion in self.task_sequence_worker:
                self._push_pending_message(result=result, promotion=promotion)

        self.preload()
        if self.is_pending():
            tarnished.execute(sequence=run)


@logger.catch()
def build_claimer(mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"] = "epic-games"):
    logger.info(f">> STARTUP SynergyTunnel - Pattern=False")
    if mode == "epic-games":
        with GameClaimerInstance() as claimer:
            claimer.just_do_it()
    elif mode == "unreal":
        with UnrealClaimerInstance() as claimer:
            claimer.just_do_it()
