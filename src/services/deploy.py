# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import asyncio
import random
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from gevent.queue import Queue

from services.bricklayer import GameClaimer
from services.bricklayer import UnrealClaimer
from services.bricklayer.exceptions import CookieRefreshException
from services.explorer import Explorer
from services.settings import (
    logger,
    MESSAGE_PUSHER_SETTINGS,
    PLAYER,
    ACTIVE_SERVERS,
    ACTIVE_PUSHERS,
)
from services.utils import ToolBox, get_challenge_ctx, MessagePusher, AshFramework


class SteelTorrent(AshFramework):
    """加速嵌套循环"""

    def __init__(self, docker, ctx_cookies, explorer, bricklayer, task_queue_pending):
        super().__init__(docker=docker)

        self.ctx_cookies = ctx_cookies
        self.explorer = explorer
        self.bricklayer: GameClaimer = bricklayer
        self.task_queue_pending = task_queue_pending
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.127 Safari/537.36 Edg/100.0.1185.44",
            "cookie": ToolBox.transfer_cookies(self.ctx_cookies),
        }

    def in_library(self, content) -> bool:
        result = self.explorer.game_manager.is_my_game(self.ctx_cookies, None, content)
        if not result["status"] and result["assert"] != "AssertObjectNotFound":
            return False
        return True

    async def parse_free_dlc(self, game_page_content, session):
        dlc_page = self.bricklayer.has_attach(game_page_content)
        if not dlc_page:
            return

        async with session.get(dlc_page, headers=self.headers) as response:
            content = await response.read()
            if not self.bricklayer.has_free_dlc(content):
                return
            dlc_details = self.bricklayer.parse_free_dlc_details(
                url=response.url, status_code=response.status, content=content
            )
            for dlc in dlc_details:
                self.worker.put(dlc)

    async def control_driver(self, context, session=None):
        # 判断游戏本体是否在库
        async with session.get(context["url"], headers=self.headers) as response:
            content = await response.read()
            context["in_library"] = self.in_library(content)
            self.task_queue_pending.put_nowait(context)
        # 识别免费附加内容
        if not context.get("review"):
            await self.parse_free_dlc(content, session)

    async def advance(self, workers):
        await super().subvert(workers)


class ClaimerScheduler:
    """系统任务调度器"""

    def __init__(self, silence: Optional[bool] = None, unreal: Optional[bool] = False):
        self.action_name = "AwesomeScheduler"
        self.end_date = datetime.now(pytz.timezone("Asia/Shanghai")) + timedelta(days=180)
        self.silence = silence
        self.unreal = unreal

        # 服务注册
        self.scheduler = BlockingScheduler()
        self.logger = logger

    def deploy_on_vps(self):
        """部署最佳实践的 VPS 定时任务"""

        # [⏰] 北京时间每周五凌晨 4 点的 两个任意时刻 执行任务
        jitter_minute = [random.randint(10, 20), random.randint(35, 57)]

        # [⚔] 首发任务用于主动认领，备用方案用于非轮询审核
        self.scheduler.add_job(
            func=self.job_loop_claim,
            trigger=CronTrigger(
                day_of_week="fri",
                hour="4",
                minute=f"{jitter_minute[0]},{jitter_minute[-1]}",
                second="30",
                timezone="Asia/Shanghai",
                # 必须使用 `end_date` 续订生产环境 定时重启
                end_date=self.end_date,
                # 必须使用 `jitter` 弥散任务发起时间
                jitter=15,
            ),
            name="loop_claim",
        )

        self.logger.debug(
            ToolBox.runtime_report(
                motive="JOB",
                action_name=self.action_name,
                message=f"任务将在北京时间每周五 04:{jitter_minute[0]} "
                f"以及 04:{jitter_minute[-1]} 执行。",
                end_date=str(self.end_date),
            )
        )

        # [⚔] Gracefully run scheduler.`
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, EOFError):
            self.scheduler.shutdown(wait=False)
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="EXITS",
                    action_name=self.action_name,
                    message="Received keyboard interrupt signal.",
                )
            )

    def deploy_jobs(self, platform: Optional[str] = None):
        """部署系统任务"""
        if platform is not None:
            self.logger.warning(
                ToolBox.runtime_report(
                    motive="MODIFY",
                    action_name=self.action_name,
                    message="deploy_jobs.platform 参数已弃用，自动修正为 `vps`",
                )
            )
        platform = "vps"

        self.logger.debug(
            ToolBox.runtime_report(
                motive="JOB",
                action_name=self.action_name,
                message="部署任务调度器",
                platform=platform.upper(),
            )
        )

        # [⚔] Distribute common state machine patterns
        if platform == "vps":
            self.deploy_on_vps()

    def job_loop_claim(self, log_ignore: Optional[bool] = False):
        """wrap function for claimer instance"""
        if not self.unreal:
            with GameClaimerInstance(
                silence=self.silence, log_ignore=log_ignore
            ) as claimer:
                claimer.just_do_it()
        else:
            with UnrealClaimerInstance(
                silence=self.silence, log_ignore=log_ignore
            ) as claimer:
                claimer.just_do_it()


class BaseInstance:
    """Atomic Scheduler"""

    def __init__(
        self,
        silence: bool,
        log_ignore: Optional[bool] = False,
        action_name: Optional[str] = None,
    ):
        """

        :param silence:
        :param log_ignore: 过滤掉已在库的资源实体的推送信息。
        """
        self.silence = silence
        self.log_ignore = log_ignore
        self.action_name = "AwesomeInstance" if action_name is None else action_name

        # 广度优先|深度优先
        self.depth = 0
        self.indepth: Optional[bool] = True
        # 服务注册
        self.logger = logger
        self.bricklayer = GameClaimer(silence=silence)
        # 尚未初始化的挑战者上下文容器
        self._ctx_session = None
        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.task_queue_pending = Queue()
        self.task_queue_worker = Queue()
        # 消息队列 按序缓存认领任务的执行状态
        self.pusher_settings = MESSAGE_PUSHER_SETTINGS
        self.message_queue = Queue()
        # 内联数据容器 编排推送模版
        self.inline_docker = []
        # 资源在库状态简写
        self.ok = self.bricklayer.assert_.GAME_OK
        self.coco = self.bricklayer.assert_.GAME_CLAIM
        self.oreo = self.bricklayer.assert_.GAME_PENDING
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
        try:
            _manager = self.bricklayer.cookie_manager
            if _manager.refresh_ctx_cookies(keep_live=True, silence=self.silence):
                self._ctx_session = self.bricklayer.cookie_manager.ctx_session
                self._ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()
            if self._ctx_cookies is None:
                self._bad_omen(CookieRefreshException.__doc__)
        except Exception as err:  # skipcq
            self._bad_omen(err.__doc__)
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

    def _pusher_putter(self, result: str, obj: Dict[str, Union[bool, str]]):
        _runtime = {"status": result, **obj, "dlc": obj.get("dlc", False)}
        self.message_queue.put_nowait(_runtime)

    def _pusher_wrapper(self):
        while not self.message_queue.empty():
            context = self.message_queue.get()
            # 过滤已在库的游戏资源的推送数据
            if self.log_ignore is True and context["status"] == self.ok:
                continue
            self.inline_docker.append(context)

        # 在 `ignore` 模式下当所有资源实体都已在库时不推送消息
        if (
            self.inline_docker
            and self.pusher_settings.get("enable")
            and any(ACTIVE_SERVERS)
        ):
            with MessagePusher(ACTIVE_SERVERS, PLAYER, self.inline_docker):
                self.logger.success(
                    ToolBox.runtime_report(
                        motive="Notify",
                        action_name=self.action_name,
                        message="推送运行报告",
                        active_pusher=ACTIVE_PUSHERS,
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
        self.inline_docker = [
            {
                "status": "🎃 领取失败",
                "name": f"error={err_message}",
                "url": "https://images4.alphacoders.com/668/thumb-1920-668521.jpg",
            }
        ]
        with MessagePusher(ACTIVE_SERVERS, PLAYER, self.inline_docker):
            self.logger.error(
                ToolBox.runtime_report(
                    motive="Notify",
                    action_name=self.action_name,
                    message="推送运行日志",
                    active_pusher=ACTIVE_PUSHERS,
                    err=err_message,
                )
            )
        sys.exit()

    def is_pending(self) -> Optional[bool]:
        """是否可发起驱动任务 True:执行 False/None:结束"""
        if self.task_queue_worker.empty() or self.depth >= 2:
            return
        if self._ctx_session is None:
            self._ctx_session = get_challenge_ctx(self.silence)

        return True

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

    def promotions_splitter(self):
        """实体分治 <已在库><领取成功><待领取>"""
        while not self.task_queue_pending.empty():
            resource_obj = self.task_queue_pending.get()
            # 实例已在库
            if resource_obj["in_library"]:
                # 初见判断在库，资源已在库；多轮判断在库，资源领取成功
                if self.depth == 0:
                    result = self.ok
                    message = "🛴 资源已在库"
                else:
                    result = self.coco
                    message = "🥂 领取成功"
                self._pusher_putter(result=result, obj=resource_obj)
                self.logger.info(
                    ToolBox.runtime_report(
                        motive="GET",
                        action_name=self.action_name,
                        message=message,
                        game=f"『{resource_obj['name']}』",
                    )
                )
            # 待领取资源 将实例移动至 worker 分治队列
            else:
                self.task_queue_worker.put(resource_obj)
                if self.depth == 0:
                    self.logger.debug(
                        ToolBox.runtime_report(
                            motive="STARTUP",
                            action_name=self.action_name,
                            message=f"🍜 发现{self.tag}",
                            game=f"『{resource_obj['name']}』",
                            indepth=self.indepth,
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
        if self.is_pending() is True:
            self.inline_bricklayer()
            # [🛵] 接下来，跳跃很有用
            if self.indepth is True:
                self.depth += 1
                return self.just_do_it()

    def inline_bricklayer(self):
        """扬帆起航"""


class GameClaimerInstance(BaseInstance):
    """单步子任务 认领周免游戏"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False):
        super(GameClaimerInstance, self).__init__(silence, log_ignore, "GameClaimer")

        self.explorer = Explorer(silence=silence)

        self.cookie = None
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.127 Safari/537.36 Edg/100.0.1185.44"
        }
        self.promotions_review = []
        self.promotions_context = []
        self.steel_torrent = None

    def __enter__(self):
        super().__enter__()
        self.cookie = ToolBox.transfer_cookies(self._ctx_cookies)
        self.headers.update({"cookie": self.cookie})

        # 初始化协同任务
        self.promotions_context = [
            {"url": p[0], "name": p[-1]} for p in self.get_promotions().items()
        ]

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        self.steel_torrent = SteelTorrent(
            docker=self.promotions_context,
            ctx_cookies=self._ctx_cookies,
            explorer=self.explorer,
            bricklayer=self.bricklayer,
            task_queue_pending=self.task_queue_pending,
        )

        return self

    def _indepth_action(self):
        self.bricklayer.claim_mode = self.bricklayer.CLAIM_MODE_ADD

        self.bricklayer.cart_balancing(
            ctx_cookies=self._ctx_cookies, ctx_session=self._ctx_session
        )
        while not self.task_queue_worker.empty():
            job = self.task_queue_worker.get()
            self.bricklayer.claim_stabilizer(
                page_link=job["url"],
                ctx_cookies=self._ctx_cookies,
                ctx_session=self._ctx_session,
            )
            job["review"] = True
            self.promotions_review.append(job)
        self.bricklayer.empty_shopping_payment(
            ctx_cookies=self._ctx_cookies, ctx_session=self._ctx_session
        )

    def _breadth_action(self):
        self.indepth = False
        self.bricklayer.claim_mode = self.bricklayer.CLAIM_MODE_GET

        job = self.task_queue_worker.get()
        result = self.bricklayer.claim_stabilizer(
            page_link=job["url"],
            ctx_cookies=self._ctx_cookies,
            ctx_session=self._ctx_session,
        )
        self._pusher_putter(result=result, obj=job)

    def get_promotions(self) -> Optional[Dict[str, Union[List[str], str]]]:
        """获取促销信息的顶级接口"""
        try:
            return self.explorer.get_promotions(ctx_cookies=self._ctx_cookies)
        except Exception as err:  # skipcq: - 应力表达式的无感切换
            self.logger.exception(err)
            return self.explorer.get_promotions_by_stress_expressions(
                ctx_session=self._ctx_session
            )

    def promotions_filter(self):
        if self.promotions_review:
            self.steel_torrent.docker = self.promotions_review
        # 启动最高功率的协同任务
        if sys.platform.startswith("win") or "cygwin" in sys.platform:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(self.steel_torrent.advance(workers="fast"))
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.steel_torrent.advance(workers="fast"))

    def inline_bricklayer(self):
        # 针对不同的应用场景优选执行策略
        if self.task_queue_worker.qsize() == 1:
            self._breadth_action()
        else:
            self._indepth_action()


class UnrealClaimerInstance(BaseInstance):
    """虚幻商城月供砖家"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False):
        super().__init__(silence, log_ignore, "UnrealClaimer")
        self.bricklayer = UnrealClaimer(silence=silence)

    def promotions_filter(self):
        content_objs = self.bricklayer.get_claimer_response(self._ctx_cookies)
        for content_obj in content_objs:
            self.task_queue_pending.put(content_obj)

    def inline_bricklayer(self):
        """虚幻商城月供砖家"""
        self.bricklayer.claim_stabilizer(
            ctx_session=self._ctx_session, ctx_cookies=self._ctx_cookies
        )
