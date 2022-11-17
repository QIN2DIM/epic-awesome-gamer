# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import random
import sys
import time
import typing
from dataclasses import dataclass
from queue import Queue

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from playwright.sync_api import BrowserContext
from playwright.sync_api import Error as NinjaException

from services.bricklayer.game import GameClaimer, empower_games_claimer
from services.bricklayer.unreal import UnrealClaimer
from services.explorer.explorer import Explorer, PermissionsHistory
from services.settings import config, DIR_EXPLORER, __version__
from services.utils.pusher import MessagePusher, MessageBody, MessageQueue
from services.utils.toolbox import fire


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
    promotion_sequence: typing.List[Promotion] = None

    def __post_init__(self):
        self.promotion_sequence = self.promotion_sequence or []

    def new_promotion(self, **kwargs):
        self.promotion_sequence.append(Promotion(**kwargs))


class ClaimerScheduler:
    """系统任务调度器"""

    def __init__(
        self, silence: typing.Optional[bool] = None, unreal: typing.Optional[bool] = False
    ):
        self.action_name = "AwesomeScheduler"
        self.silence = silence
        self.unreal = unreal

        # 服务注册
        self._scheduler = BackgroundScheduler()
        self._job = None
        self._job_id = "tango"
        self.logger = logger

    def deploy_on_vps(self):
        jitter_minute = [random.randint(10, 20), random.randint(35, 57)]

        # [⚔] 首发任务用于主动认领，备用方案用于非轮询审核
        self._job: Job = self._scheduler.add_job(
            func=self._on_job_claim,
            trigger=CronTrigger(
                day_of_week="fri",
                hour="0",
                minute=f"{jitter_minute[0]},{jitter_minute[-1]}",
                timezone="Asia/Shanghai",
                jitter=15,
            ),
            id=self._job_id,
        )

        # [⚔] Gracefully run scheduler.
        self._scheduler.start()
        logger.info(f">> JOB [{self.action_name}] - next_run_time={self._job.next_run_time}")

        try:
            while True:
                time.sleep(3600)
        except (KeyboardInterrupt, EOFError):
            self._scheduler.shutdown()
            logger.debug(f">> EXITS [{self.action_name}] Received keyboard interrupt signal")

    def _on_job_claim(self):
        self.job_loop_claim(log_ignore=False)
        logger.success(f">> OFFLOAD [{self.action_name}] Job has been safely released")

    def job_loop_claim(self, log_ignore: typing.Optional[bool] = False):
        """wrap function for claimer instance"""
        logger.info(
            f">> STARTUP [{self.action_name}] SynergyTunnel - version={__version__} Pattern=False"
        )
        if self.unreal:
            with UnrealClaimerInstance(self.silence, log_ignore=log_ignore) as claimer:
                claimer.just_do_it()
        else:
            with GameClaimerInstance(self.silence, log_ignore=log_ignore) as claimer:
                claimer.just_do_it()


class BaseInstance:
    """Atomic Scheduler"""

    def __init__(
        self,
        silence: bool,
        log_ignore: typing.Optional[bool] = False,
        action_name: typing.Optional[str] = None,
    ):
        """

        :param silence:
        :param log_ignore: 过滤掉已在库的资源实体的推送信息。
        """
        self.silence = silence
        self.log_ignore = log_ignore
        self.action_name = "AwesomeInstance" if action_name is None else action_name

        # 服务注册
        self.logger = logger
        self.bricklayer = GameClaimer(
            email=config.epic_email, password=config.epic_password, silence=silence
        )
        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.promotions = Promotions()
        self.task_queue_pending = Queue()
        self.task_sequence_worker = []
        # 消息队列 按序缓存认领任务的执行状态
        self.pusher_settings = config.message_pusher
        self.message_queue = MessageQueue()
        self.inline_docker: typing.List[MessageBody] = []
        # 资源在库状态简写
        self.in_library = self.bricklayer.assert_util.GAME_OK
        self.claimed = self.bricklayer.assert_util.GAME_CLAIM
        # 增加日志可读性
        if "game" in self.action_name.lower():
            self.tag = "周免游戏"
        elif "unreal" in self.action_name.lower():
            self.tag = "月免内容"
        else:
            self.tag = "免费资源"

        self._ctx_cookies = None

    def __enter__(self):
        """激活挑战者并获取身份令牌"""
        manager = self.bricklayer.cookie_manager
        if not manager.has_available_token:
            try:
                fire(  # token
                    containers=manager.refresh_ctx_cookies,
                    path_state=manager.path_ctx_cookies,
                    user_data_dir=manager.user_data_dir,
                    iframe_content_window=True,
                )
            except NinjaException as err:
                logger.exception(err)
                self._bad_omen(str(err))
        self._ctx_cookies = manager.load_ctx_cookies()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._pusher_wrapper()

    def _push_pending_message(self, result, promotion: Promotion):
        element = MessageBody(url=promotion.url, title=promotion.title, result=result, dlc=False)
        self.message_queue.put(element)

    def _pusher_wrapper(self):
        while not self.message_queue.empty():
            element: MessageBody = self.message_queue.get()
            # 过滤已在库的游戏资源的推送数据
            if self.log_ignore is True and element.result == self.in_library:
                continue
            self.inline_docker.append(element)

        # 在 `ignore` 模式下当所有资源实体都已在库时不推送消息
        if (
            self.inline_docker
            and self.pusher_settings.enable
            and any(self.pusher_settings.ACTIVE_SERVERS)
        ):
            with MessagePusher(
                servers=self.pusher_settings.ACTIVE_SERVERS,
                player=self.pusher_settings.player,
                inline_docker=self.inline_docker,
                key_images=Explorer.cdn_image_urls,
            ):
                logger.success(
                    f">> Notify [{self.action_name}] 推送运行报告 - "
                    f"active_pusher={self.pusher_settings.ACTIVE_PUSHERS}"
                )
        # 在 `ignore` 模式下追加 DEBUG 标签日志
        elif self.log_ignore:
            logger.debug(
                f">> Notify [{self.action_name}] 忽略已在库的资源实体推送信息 - ignore={self.log_ignore}"
            )

    def _bad_omen(self, err_message=None):
        preview_link = "https://images2.alphacoders.com/127/1276555.png"
        element = MessageBody(url=preview_link, title=f"error={err_message}", result="🎃 领取失败")
        with MessagePusher(
            servers=self.pusher_settings.ACTIVE_SERVERS,
            player=self.pusher_settings.player,
            inline_docker=[element],
            key_images=[preview_link],
        ):
            logger.error(
                f">> Notify [{self.action_name}] 推送运行日志 - "
                f"active_pusher={self.pusher_settings.ACTIVE_PUSHERS} err={err_message}"
            )
        sys.exit()

    def is_pending(self) -> typing.Optional[bool]:
        """是否可发起驱动任务 True:执行 False/None:结束"""
        return self.task_sequence_worker and self._ctx_cookies


class GameClaimerInstance(BaseInstance):
    """单步子任务 认领周免游戏"""

    def __init__(self, silence: bool, log_ignore: typing.Optional[bool] = False):
        super(GameClaimerInstance, self).__init__(silence, log_ignore, "GameClaimer")
        self.explorer = Explorer()

        # Pending order history
        self.dir_hook = DIR_EXPLORER
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

    def __enter__(self):
        return self

    def get_promotions(self) -> typing.List[Promotion]:
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
                logger.debug(
                    f">> Checkout [{self.action_name}] {promotion.title} - state=已在库中 link={promotion.url}"
                )
            else:
                self.task_sequence_worker.append(promotion)
                logger.debug(
                    f">> Checkout [{self.action_name}] {promotion.title} - state=待认领 link={promotion.url}"
                )
            promotion.in_library = in_library
        return self.task_sequence_worker

    def just_do_it(self):
        def recur_order_history(state: str, promotion: Promotion):
            if state in [self.bricklayer.utils.GAME_OK, self.bricklayer.assert_util.GAME_CLAIM]:
                self.ph.namespaces.add(promotion.namespace)
                self.task_sequence_worker.remove(promotion)
                self.ph.save_order_history()

        def run(context: BrowserContext):
            context.storage_state(path=self.bricklayer.cookie_manager.path_ctx_cookies)
            promotions = self.preload()
            page = context.new_page()
            for promotion in promotions:
                self.bricklayer.promotion_url2title[promotion.url] = promotion.title
                result = empower_games_claimer(self.bricklayer, promotion.url, page, pattern="get")
                self._push_pending_message(result=result, promotion=promotion)
                recur_order_history(result, promotion)

        fire(
            containers=[self.bricklayer.cookie_manager.refresh_ctx_cookies, run],
            path_state=self.bricklayer.cookie_manager.path_ctx_cookies,
            user_data_dir=self.bricklayer.cookie_manager.user_data_dir,
        )


class UnrealClaimerInstance(BaseInstance):
    """虚幻商城月供砖家"""

    def __init__(self, silence: bool, log_ignore: typing.Optional[bool] = False):
        super().__init__(silence, log_ignore, "UnrealClaimer")
        self.bricklayer = UnrealClaimer(email=config.epic_email, password=config.epic_password)

    def get_promotions(self) -> typing.List[Promotion]:
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
                logger.debug(
                    f">> CHECKOUT [{self.action_name}] {promotion.title} - state=已在库中 link={promotion.url}"
                )
            else:
                self.task_sequence_worker.append(promotion)
                logger.debug(
                    f">> CHECKOUT [{self.action_name} {promotion.title}] - state=待认领 link={promotion.url}"
                )

    def just_do_it(self):
        def run(context: BrowserContext):
            result = self.bricklayer.get_free_content(page=context.new_page())
            for promotion in self.task_sequence_worker:
                self._push_pending_message(result=result, promotion=promotion)

        self.preload()
        if self.is_pending():
            fire(
                containers=run,
                path_state=self.bricklayer.cookie_manager.path_ctx_cookies,
                user_data_dir=self.bricklayer.cookie_manager.user_data_dir,
            )
