# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import sys
import time
import typing

import yaml
from loguru import logger

from services.bricklayer.game import GameClaimer, claim_stabilizer
from services.explorer.core import new_store_explorer, GamePool, Game
from services.explorer.explorer import Explorer
from services.settings import config, DIR_EXPLORER
from services.utils.pusher import MessageBody, MessagePusher
from services.utils.toolbox import get_challenge_ctx
from os.path import isfile, getmtime


class YouKnowWhoIAm:
    def __init__(self, dir_hook: str = DIR_EXPLORER):
        self.dir_hook = dir_hook

        self.path_order_history = ""
        self.path_ctx_store = ""
        self.total_free_games = 0
        self.outdated_interval_order_history = 86400
        self.outdated_interval_ctx_store = 259200
        self.player = config.message_pusher.player
        self.namespaces: typing.Set[str] = set()
        self.inline_docker: typing.List[MessageBody] = []
        self.key_images: typing.List[str] = []

        self.game_pool = GamePool()
        self.claimer = GameClaimer(
            email=config.epic_email,
            password=config.epic_password,
            claim_mode=GameClaimer.CLAIM_MODE_ADD,
        )

        self._ctx_cookies = None
        self._ctx_session = None

    def __enter__(self):
        _manager = self.claimer.cookie_manager
        if _manager.refresh_ctx_cookies(keep_live=True, silence=False):
            self._ctx_session = self.claimer.cookie_manager.ctx_session
            self._ctx_cookies = self.claimer.cookie_manager.load_ctx_cookies()
        if not self._ctx_cookies:
            sys.exit()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 推送消息
        self.push_all_message()
        # 关闭挑战者上下文
        try:
            if self._ctx_session:
                self._ctx_session.quit()
        except AttributeError:
            pass
        # 缓存订单历史
        self.save_order_history()

    def get_ctx_store(self):
        suffix = self.claimer.cookie_manager.hash
        path_ctx_store = os.path.join(self.dir_hook, f"ctx_store_{suffix}.yaml")
        self.path_ctx_store = path_ctx_store

        # 读取 path_ctx_store 本地缓存（72h有效）
        if isfile(path_ctx_store):
            modify_interval = time.time() - getmtime(path_ctx_store)
            if modify_interval < self.outdated_interval_ctx_store:
                with open(path_ctx_store, "r", encoding="utf8") as file:
                    if data := yaml.safe_load(file):
                        try:
                            for game in data["_games"]:
                                self.game_pool.put(**game)
                                self.total_free_games += 1
                            logger.info("加载历史商城数据")
                        except (TypeError, AttributeError):
                            pass

        # 获取商城免费游戏数据
        if self.game_pool.empty():
            logger.info("更新商城数据")
            self._ctx_session = self._ctx_session or get_challenge_ctx()
            store_explorer = new_store_explorer(self._ctx_cookies, self._ctx_session)
            store_explorer.discovery_free_games(game_pool=self.game_pool)
            with open(path_ctx_store, "w", encoding="utf8") as file:
                yaml.safe_dump(self.game_pool.to_dict(), file)
            self.total_free_games = store_explorer.total_free_games

    def get_oder_history(self):
        suffix = self.claimer.cookie_manager.hash
        path_order_history = os.path.join(self.dir_hook, f"order_history_{suffix}.yaml")
        self.path_order_history = path_order_history

        # 加载缓存的订单数据（24小时有效）
        if isfile(path_order_history):
            modify_time = time.time() - os.path.getmtime(path_order_history)
            if modify_time < self.outdated_interval_order_history:
                with open(path_order_history, "r", encoding="utf8") as file:
                    if data := yaml.safe_load(file):
                        try:
                            self.namespaces = data
                            logger.info("加载历史订单数据")
                        except (TypeError, AttributeError):
                            pass

        # 获取玩家历史订单数据
        if not self.namespaces:
            logger.info("更新订单数据")
            explorer = Explorer()
            if resp := explorer.get_order_history(self._ctx_cookies):
                pages = int((explorer.orders_count * 1.2 - len(resp)) / 10) + 1
                for page in range(1, pages + 1):
                    explorer.get_order_history(self._ctx_cookies, page=str(page))
                self.namespaces = explorer.namespaces

        # 緩存歷史訂單數據
        self.save_order_history()

    def offload(self, task_list):
        if not task_list:
            return

        # 檢查挑戰者上下文的備戰狀態
        self._ctx_session = self._ctx_session or get_challenge_ctx()
        # 在任务发起前将购物车内商品移至愿望清单
        self.claimer.cart_balancing(self._ctx_cookies, self._ctx_session)
        # CLAIM_MODE_ADD 将未领取的促销实体逐项移至购物车后一并处理
        for game in task_list:
            self.claimer.promotion2result[game.url] = game.title
            result = claim_stabilizer(self.claimer, game.url, self._ctx_cookies, self._ctx_session)
            if result == self.claimer.assert_.GAME_PENDING:
                result = self.claimer.assert_.GAME_CLAIM
            self.set_pending_message(game, result)
        self.claimer.empty_shopping_payment(self._ctx_cookies, self._ctx_session, from_get=True)

    def set_pending_message(self, game: Game, result):
        self.inline_docker.append(MessageBody(url=game.url, title=game.title, result=result))
        self.key_images.append(game.image_url)
        self.namespaces.add(game.namespace)

    def push_all_message(self):
        active_servers = config.message_pusher.ACTIVE_SERVERS
        active_pusher = config.message_pusher.ACTIVE_PUSHERS
        with MessagePusher(
            servers=active_servers,
            player=self.player,
            inline_docker=self.inline_docker,
            key_images=self.key_images,
        ):
            logger.info(f"Notify [MessagePusher] 推送运行日志 - {active_pusher=}")

    def save_order_history(self):
        with open(self.path_order_history, "w", encoding="utf8") as file:
            yaml.safe_dump(self.namespaces, file)

    def attach(self):
        self.get_ctx_store()
        self.get_oder_history()

        task_list = self.game_pool.filter_games(self.namespaces)
        logger.info(f"当前玩家 {self.player} 可领取 {self.total_free_games} 款常驻免费游戏")
        logger.info(f"当前玩家 {self.player} 仍有 {len(task_list)} 款免费游戏尚未领取")

        self.offload(task_list=task_list)
