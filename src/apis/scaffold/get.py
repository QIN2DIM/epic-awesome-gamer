# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
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


class YouKnowWhoIAm:
    def __init__(self, dir_hook: str = DIR_EXPLORER):
        self.dir_hook = dir_hook
        self.player = config.message_pusher.player
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.push_all_message()
        try:
            if self._ctx_session:
                self._ctx_session.quit()
        except AttributeError:
            pass

    def get_ctx_store(self):
        suffix = self.claimer.cookie_manager.hash
        path_order_history = os.path.join(f"order_history_{suffix}.yaml")

        total_free_games = 0

        # 读取 path_order_history 本地缓存（24h有效）
        if (
            os.path.isfile(path_order_history)
            and time.time() - os.path.getmtime(path_order_history) < 86400
        ):
            logger.info("加载历史商城数据")
            with open(path_order_history, "r", encoding="utf8") as file:
                if data := yaml.safe_load(file):
                    for game in data["_games"]:
                        self.game_pool.put(**game)
                        total_free_games += 1

        # 获取商城免费游戏数据
        if self.game_pool.empty():
            self._ctx_session = self._ctx_session or get_challenge_ctx()
            logger.info("更新商城数据")
            store_explorer = new_store_explorer(self._ctx_cookies, self._ctx_session)
            store_explorer.discovery_free_games(game_pool=self.game_pool)
            with open(path_order_history, "w", encoding="utf8") as file:
                yaml.safe_dump(self.game_pool.to_dict(), file)
            total_free_games = store_explorer.total_free_games

        logger.info(f"当前玩家 {self.player} 可领取 {total_free_games} 款常驻免费游戏")

    def get_oder_history(self) -> typing.Set[str]:
        """获取未在库游戏的数据对象"""
        explorer = Explorer()

        # 获取玩家历史订单数据
        if resp := explorer.get_order_history(self._ctx_cookies):
            pages = int((explorer.orders_count * 1.2 - len(resp)) / 10) + 1
            for page in range(1, pages + 1):
                explorer.get_order_history(self._ctx_cookies, page=str(page))
            # 缓存订单数据
            suffix = self.claimer.cookie_manager.hash
            path_ctx_store = os.path.join(self.dir_hook, f"ctx_store_{suffix}.yaml")
            with open(path_ctx_store, "w", encoding="utf8") as file:
                yaml.safe_dump(explorer.namespaces, file)
        return explorer.namespaces

    def offload(self, namespaces: typing.Set[str]):
        task_list = self.game_pool.filter_games(namespaces)
        logger.info(f"当前玩家 {self.player} 仍有 {len(task_list)} 款免费游戏尚未领取")

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
        self.claimer.empty_shopping_payment(self._ctx_cookies, self._ctx_session)

    def set_pending_message(self, game: Game, result):
        self.inline_docker.append(MessageBody(url=game.url, title=game.title, result=result))
        self.key_images.append(game.image_url)

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

    def attach(self):
        if self._ctx_cookies:
            self.get_ctx_store()
            namespaces = self.get_oder_history()
            self.offload(namespaces)
