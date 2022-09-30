# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
import sys
import time
import typing
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytz
from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from gevent.queue import Queue
from loguru import logger

from services.bricklayer.exceptions import CookieRefreshException
from services.bricklayer.game import GameClaimer, claim_stabilizer
from services.bricklayer.unreal import UnrealClaimer
from services.explorer.explorer import Explorer
from services.settings import config
from services.utils.pusher import MessagePusher, MessageBody, MessageQueue
from services.utils.toolbox import ToolBox, get_challenge_ctx


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
    promotions: typing.List[Promotion] = None

    def __post_init__(self):
        self.promotions = self.promotions or []

    def new_promotion(self, **kwargs):
        self.promotions.append(Promotion(**kwargs))


class ClaimerScheduler:
    """系统任务调度器"""

    def __init__(
        self, silence: typing.Optional[bool] = None, unreal: typing.Optional[bool] = False
    ):
        self.action_name = "AwesomeScheduler"
        self.end_date = datetime.now(pytz.timezone("Asia/Shanghai")) + timedelta(days=360)
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
                end_date=self.end_date,
                jitter=15,
            ),
            id=self._job_id,
        )

        # [⚔] Gracefully run scheduler.
        self._scheduler.start()
        self.logger.info(
            ToolBox.runtime_report(
                motive="JOB", action_name=self.action_name, next_run_time=self._job.next_run_time
            )
        )
        try:
            while True:
                time.sleep(3600)
        except (KeyboardInterrupt, EOFError):
            self._scheduler.shutdown()
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="EXITS",
                    action_name=self.action_name,
                    message="Received keyboard interrupt signal.",
                )
            )

    def _on_job_claim(self):
        self.job_loop_claim(log_ignore=False)
        self.logger.success(
            ToolBox.runtime_report(self.action_name, "OFFLOAD", "Job has been safely released")
        )
        try:
            next_run_time = self._job.next_run_time
        except AttributeError:
            next_run_time = None
        self.logger.info(
            ToolBox.runtime_report(
                motive="JOB", action_name=self.action_name, next_run_time=next_run_time
            )
        )

    def job_loop_claim(self, log_ignore: typing.Optional[bool] = False):
        """wrap function for claimer instance"""
        self.logger.info(
            ToolBox.runtime_report(self.action_name, "STARTUP", "SynergyTunnel Pattern: True")
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
        # 尚未初始化的挑战者上下文容器
        self._ctx_session = None
        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.promotions = Promotions()
        self.task_queue_pending = Queue()
        self.task_queue_worker = Queue()
        # 消息队列 按序缓存认领任务的执行状态
        self.pusher_settings = config.message_pusher
        self.message_queue = MessageQueue()
        self.inline_docker: typing.List[MessageBody] = []
        # 资源在库状态简写
        self.in_library = self.bricklayer.assert_.GAME_OK
        self.claimed = self.bricklayer.assert_.GAME_CLAIM
        # 增加日志可读性
        if "game" in self.action_name.lower():
            self.tag = "周免游戏"
        elif "unreal" in self.action_name.lower():
            self.tag = "月免内容"
        else:
            self.tag = "免费资源"

        self._ctx_session = None
        self._ctx_cookies = None

    def __enter__(self):
        """激活挑战者并获取身份令牌"""
        try:
            _manager = self.bricklayer.cookie_manager
            if _manager.refresh_ctx_cookies(keep_live=True, silence=self.silence):
                self._ctx_session = self.bricklayer.cookie_manager.ctx_session
                self._ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()
            if self._ctx_cookies is None:
                raise CookieRefreshException
        except CookieRefreshException as err:
            self._bad_omen(err.__doc__)
        except Exception as err:  # skipcq
            self.logger.exception(err)
            self._bad_omen(str(err))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 消息推送
        self._pusher_wrapper()

        # 缓存卸载
        try:
            if self._ctx_session:
                self._ctx_session.quit()
        except AttributeError:
            pass

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
                self.logger.success(
                    ToolBox.runtime_report(
                        motive="Notify",
                        action_name=self.action_name,
                        message="推送运行报告",
                        active_pusher=self.pusher_settings.ACTIVE_PUSHERS,
                    )
                )
        # 在 `ignore` 模式下追加 DEBUG 标签日志
        elif self.log_ignore:
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="Notify",
                    action_name=self.action_name,
                    message="忽略已在库的资源实体推送信息",
                    ignore=self.log_ignore,
                )
            )

    def _bad_omen(self, err_message=None):
        preview_link = "https://images4.alphacoders.com/668/thumb-1920-668521.jpg"
        element = MessageBody(url=preview_link, title=f"error={err_message}", result="🎃 领取失败")

        with MessagePusher(
            servers=self.pusher_settings.ACTIVE_SERVERS,
            player=self.pusher_settings.player,
            inline_docker=[element],
            key_images=[preview_link],
        ):
            self.logger.error(
                ToolBox.runtime_report(
                    motive="Notify",
                    action_name=self.action_name,
                    message="推送运行日志",
                    active_pusher=self.pusher_settings.ACTIVE_PUSHERS,
                    err=err_message,
                )
            )
        sys.exit()

    def is_pending(self) -> typing.Optional[bool]:
        """是否可发起驱动任务 True:执行 False/None:结束"""
        if self.task_queue_worker.empty():
            return
        if self._ctx_session is None:
            self._ctx_session = get_challenge_ctx(self.silence)
        return True

    def promotions_splitter(self):
        """实体分治 <已在库><领取成功><待领取>"""
        _offload = set()
        while not self.task_queue_pending.empty():
            promotion: Promotion = self.task_queue_pending.get()

            if promotion.url in _offload:
                continue
            _offload.add(promotion.url)

            if promotion.in_library:
                self.logger.info(
                    ToolBox.runtime_report(
                        motive="GET",
                        action_name=self.action_name,
                        message=self.in_library,
                        game=f"『{promotion.title}』",
                        url=promotion.url,
                    )
                )
                self._push_pending_message(result=self.in_library, promotion=promotion)
            # 待领取资源 将实例移动至 worker 分治队列
            else:
                self.task_queue_worker.put(promotion)
                self.logger.debug(
                    ToolBox.runtime_report(
                        motive="STARTUP",
                        action_name=self.action_name,
                        message=f"🍜 发现{self.tag}",
                        game=f"『{promotion.title}』",
                        url=promotion.url,
                    )
                )

    def just_do_it(self):
        """启动接口"""
        # ======================================
        # [🚀] 你以为是武器吧？但是居然是讯息……
        # ======================================
        # 1. 获取资源<本周免费>
        # 2. 剔除资源<已在库中>
        # ======================================
        self.promotions_filter()
        self.promotions_splitter()

        # ======================================
        # [🚀] 前有重要道具！但是人机挑战……
        # ======================================
        # 1. 启动消息队列 编排消息模版
        # 2. 启动任务队列 领取周免游戏
        # ======================================
        # [🛵] 接下来，跳跃很有用
        if self.is_pending():
            self.inline_bricklayer()

    def promotions_filter(self):
        """
        促销实体过滤器

        1. 判断游戏本体是否在库
        2. 判断是否存在免费附加内容
        3. 识别并弹出已在库资源
        4. 返回待认领的实体资源
        :return:
        """
        raise NotImplementedError

    def inline_bricklayer(self):
        """扬帆起航"""


class GameClaimerInstance(BaseInstance):
    """单步子任务 认领周免游戏"""

    def __init__(self, silence: bool, log_ignore: typing.Optional[bool] = False):
        super(GameClaimerInstance, self).__init__(silence, log_ignore, "GameClaimer")
        self.explorer = Explorer(email=config.epic_email, silence=silence)

    def get_promotions(self) -> typing.List[Promotion]:
        """获取游戏促销信息"""
        promotions = self.explorer.get_promotions(self._ctx_cookies)
        for promotion in promotions:
            self.promotions.new_promotion(**promotion)
        return self.promotions.promotions

    def promotions_filter(self):
        """获取游戏在库信息"""
        # 获取历史订单数据
        order_history = self.explorer.get_order_history(self._ctx_cookies)
        # 获取周免促销数据
        promotions = self.get_promotions()
        # 标记促销实体的在库状态
        for promotion in promotions:
            promotion.in_library = order_history.get(promotion.namespace, False)
            self.task_queue_pending.put(promotion)

    def inline_bricklayer(self):
        # CLAIM_MODE_ADD 将未领取的促销实体逐项移至购物车后一并处理
        self.bricklayer.claim_mode = self.bricklayer.CLAIM_MODE_ADD
        # 在任务发起前将购物车内商品移至愿望清单
        self.bricklayer.cart_balancing(self._ctx_cookies, self._ctx_session)
        # 当存在待处理任务时启动 Bricklayer
        while not self.task_queue_worker.empty():
            promotion = self.task_queue_worker.get()
            self.bricklayer.promotion2result[promotion.url] = promotion.title
            claim_stabilizer(self.bricklayer, promotion.url, self._ctx_cookies, self._ctx_session)
            self._push_pending_message(result=self.in_library, promotion=promotion)
        self.bricklayer.empty_shopping_payment(self._ctx_cookies, self._ctx_session)


class UnrealClaimerInstance(BaseInstance):
    """虚幻商城月供砖家"""

    def __init__(self, silence: bool, log_ignore: typing.Optional[bool] = False):
        super().__init__(silence, log_ignore, "UnrealClaimer")
        self.bricklayer = UnrealClaimer(
            email=config.epic_email, password=config.epic_password, silence=silence
        )

    def get_promotions(self) -> typing.List[Promotion]:
        promotions = self.bricklayer.get_promotions(self._ctx_cookies)
        for promotion in promotions:
            self.promotions.new_promotion(**promotion)
        return self.promotions.promotions

    def promotions_filter(self):
        for promotion in self.get_promotions():
            self.task_queue_pending.put(promotion)

    def inline_bricklayer(self):
        self.bricklayer.claim_stabilizer(
            ctx_session=self._ctx_session, ctx_cookies=self._ctx_cookies
        )
        # 将无效的任务缓存出队
        while not self.task_queue_worker.empty():
            promotion = self.task_queue_worker.get()
            self._push_pending_message(result=self.in_library, promotion=promotion)
