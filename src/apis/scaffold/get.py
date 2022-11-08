# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import typing
from contextlib import suppress

from loguru import logger
from playwright.sync_api import Error as NinjaException
from playwright.sync_api import Page, BrowserContext

from services.bricklayer.game import GameClaimer, empower_games_claimer
from services.explorer.core import Game
from services.explorer.explorer import PermissionsHistory
from services.settings import config, DIR_EXPLORER
from services.utils.pusher import MessageBody, MessagePusher
from services.utils.toolbox import fire


class IReallyWantToStayAtYourHouse:
    def __init__(self, dir_hook: str = DIR_EXPLORER):
        self._ctx_cookies = None
        self.inline_docker: typing.List[MessageBody] = []
        self.player = config.message_pusher.player

        self.claimer = GameClaimer(email=config.epic_email, password=config.epic_password)
        suffix = self.claimer.cookie_manager.hash
        self.path_ctx_store = os.path.join(dir_hook, f"ctx_store_{suffix}.yaml")
        self.path_order_history = os.path.join(dir_hook, f"order_history_{suffix}.yaml")

        self.ph = PermissionsHistory(
            dir_hook=dir_hook,
            ctx_cookies=self._ctx_cookies,
            path_ctx_store=self.path_ctx_store,
            path_order_history=self.path_order_history,
        )

    def __enter__(self):
        manager = self.claimer.cookie_manager
        if not manager.has_available_token:
            with suppress(NinjaException):
                fire(
                    containers=manager.refresh_ctx_cookies,
                    path_state=manager.path_ctx_cookies,
                    user_data_dir=manager.user_data_dir,
                )
        self._ctx_cookies = manager.load_ctx_cookies()
        self.ph.ctx_cookies = self._ctx_cookies
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 推送消息
        self.push_all_message()
        # 缓存订单数据和商城数据
        self.ph.save_order_history()
        self.ph.save_ctx_store()

    def offload(self, task_list, page: Page):
        if not task_list:
            return

        # 在任务发起前将购物车内商品移至愿望清单
        self.claimer.cart_balancing(page)
        # CLAIM_MODE_ADD 将未领取的促销实体逐项移至购物车后一并处理
        for game in task_list:
            self.claimer.promotion_url2title[game.url] = game.title
            result = empower_games_claimer(self.claimer, game.url, page, pattern="add")
            if result == self.claimer.assert_util.GAME_PENDING:
                result = self.claimer.assert_util.GAME_CLAIM
            self.set_pending_message(game, result)
        self.claimer.empty_shopping_payment(page)

    def set_pending_message(self, game: Game, result):
        self.inline_docker.append(MessageBody(url=game.url, title=game.title, result=result))
        self.ph.key_images.append(game.image_url)
        self.ph.namespaces.add(game.namespace)

    def push_all_message(self):
        active_servers = config.message_pusher.ACTIVE_SERVERS
        active_pusher = config.message_pusher.ACTIVE_PUSHERS
        with MessagePusher(
            servers=active_servers,
            player=self.player,
            inline_docker=self.inline_docker,
            key_images=self.ph.key_images,
        ):
            logger.info(f"Notify [MessagePusher] 推送运行日志 - {active_pusher=}")

    def attach(self):
        def run(context: BrowserContext):
            page = context.new_page()
            self.ph.load_memory()
            self.ph.get_ctx_store(page)
            self.ph.get_oder_history(ctx_cookies=self._ctx_cookies)

            task_list = self.ph.game_pool.filter_games(self.ph.namespaces)
            logger.info(f"当前玩家 {self.player} 可领取 {self.ph.total_free_games} 款常驻免费游戏")
            logger.info(f"当前玩家 {self.player} 仍有 {len(task_list)} 款免费游戏尚未领取")

            self.offload(task_list, page)

        fire(
            containers=run,
            path_state=self.claimer.cookie_manager.path_ctx_cookies,
            user_data_dir=self.claimer.cookie_manager.user_data_dir,
        )
