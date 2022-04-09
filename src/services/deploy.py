# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
from datetime import datetime, timedelta
from typing import Optional, List

import apprise
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from gevent.queue import Queue

from services.bricklayer import Bricklayer
from services.bricklayer import UnrealClaimer
from services.explorer import Explorer
from services.settings import logger, MESSAGE_PUSHER_SETTINGS, PLAYER
from services.utils import ToolBox, get_challenge_ctx


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
        except KeyboardInterrupt:
            self.scheduler.shutdown(wait=False)
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="EXITS",
                    action_name=self.action_name,
                    message="Received keyboard interrupt signal.",
                )
            )

    def deploy_jobs(self, platform: Optional[str] = None):
        """
        部署系统任务

        :param platform: within [vps serverless qing-long]
        :return:
        """
        platform = "vps" if platform is None else platform
        if platform not in ["vps", "serverless", "qing-long"]:
            raise NotImplementedError

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
        elif platform == "serverless":
            raise NotImplementedError
        elif platform == "qing-long":
            return self.job_loop_claim()

    def job_loop_claim(self):
        """wrap function for claimer instance"""
        if not self.unreal:
            with ClaimerInstance(silence=self.silence) as claimer:
                claimer.just_do_it()
        else:
            with UnrealClaimerInstance(silence=self.silence) as claimer:
                claimer.just_do_it()


class ClaimerInstance:
    """单步子任务 认领周免游戏"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False, _auth_str=None):
        """

        :param silence:
        :param log_ignore: 过滤掉已在库的资源实体的推送信息。
        """
        self.action_name = "ClaimerInstance"
        self.silence = silence
        self.logger = logger
        self.log_ignore = log_ignore

        # 服务注册
        auth_str = "games" if _auth_str is None else _auth_str
        self.bricklayer = Bricklayer(silence=silence, auth_str=auth_str)
        self.explorer = Explorer(silence=silence)

        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.task_queue = Queue()
        # 消息队列 按序缓存认领任务的执行状态
        self.message_queue = Queue()
        # 内联数据容器 编排推送模版
        self.inline_docker = []

    def __enter__(self):
        # 集成统一的驱动上下文，减少内存占用
        self.challenger = get_challenge_ctx(silence=self.silence)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 消息推送
        self._pusher_wrapper()

        # 缓存卸载
        if hasattr(self, "challenger"):
            self.challenger.quit()

    def _pusher_wrapper(self):
        while not self.message_queue.empty():
            context = self.message_queue.get()
            # 过滤已在库的游戏资源的推送数据
            if (
                self.log_ignore is True
                and context["status"] == self.bricklayer.assert_.GAME_OK
            ):
                continue
            self.inline_docker.append(context)

        # 在 `ignore` 模式下当所有资源实体都已在库时不推送消息
        if self.inline_docker:
            self._push(inline_docker=self.inline_docker)
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

    def _push(self, inline_docker: list, pusher_settings: Optional[dict] = None):
        """
        推送追踪日志

        :param inline_docker:
        :param pusher_settings:
        :return:
        """
        # -------------------------
        # [♻]参数过滤
        # -------------------------
        if pusher_settings is None:
            pusher_settings = MESSAGE_PUSHER_SETTINGS
        if not pusher_settings["enable"]:
            return
        # -------------------------
        # [📧]消息推送
        # -------------------------
        _inline_textbox = ["<周免游戏>".center(20, "=")]
        if not inline_docker:
            _inline_textbox += [f"[{ToolBox.date_format_now()}] 🛴 暂无待认领的周免游戏"]
        else:
            _game_textbox = []
            _dlc_textbox = []
            for game_obj in inline_docker:
                if not game_obj.get("dlc"):
                    _game_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
                else:
                    _dlc_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
            _inline_textbox.extend(_game_textbox)
            if _dlc_textbox:
                _inline_textbox += ["<附加内容>".center(20, "=")]
                _inline_textbox.extend(_dlc_textbox)
        _inline_textbox += [
            "<操作统计>".center(20, "="),
            f"Player: {PLAYER}",
            f"Total: {inline_docker.__len__()}",
        ]

        # 注册 Apprise 消息推送框架
        active_pusher = pusher_settings["pusher"]
        surprise = apprise.Apprise()
        for server in active_pusher.values():
            surprise.add(server)

        # 发送模版消息
        surprise.notify(body="\n".join(_inline_textbox), title="EpicAwesomeGamer 运行报告")

        self.logger.success(
            ToolBox.runtime_report(
                motive="Notify",
                action_name=self.action_name,
                message="消息推送完毕",
                active_pusher=[i[0] for i in active_pusher.items() if i[-1]],
            )
        )

    def claim_free_game(
        self,
        challenger,
        ctx_cookies: List[dict],
        game_objs: dict,
        urls: Optional[List[str]] = None,
    ):
        """认领周免游戏"""
        if not urls:
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="SKIP",
                    action_name=self.action_name,
                    message="🛴 当前玩家暂无待认领的周免游戏。",
                )
            )
            return

        # 优先处理常规情况 urls.__len__() == 1
        for url in urls:
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="STARTUP",
                    action_name="ScaffoldClaim",
                    message="🍜 正在为玩家领取周免游戏",
                    game=f"『{game_objs[url]}』",
                )
            )

            # 更新任务队列
            challenger.switch_to.new_window("tab")
            self.task_queue.put({"game": challenger.current_window_handle})

            # 反复生产挑战者领取周免游戏
            self.bricklayer.get_free_game(
                page_link=url, ctx_cookies=ctx_cookies, _ctx_session=challenger
            )

            # 编制运行缓存 用于生成业务报告
            _runtime = {"status": self.bricklayer.result, "name": game_objs[url]}
            self.message_queue.put_nowait(_runtime)

    def claim_free_dlc(self, challenger, ctx_cookies):
        """认领周免游戏的免费附加内容"""
        while not self.task_queue.empty():
            context = self.task_queue.get()

            # {"game": WebDriver Window}
            if isinstance(context, dict) and context.get("game"):
                challenger.switch_to.window(context["game"])
                dlc_details = self.bricklayer.get_free_dlc_details(
                    _ctx_session=challenger
                )
                for dlc in dlc_details:
                    self.task_queue.put(dlc)
            # {"url": link of dlc , "name": alia-label of dlc}
            elif isinstance(context, dict) and context.get("url"):
                result = self.bricklayer.get_free_dlc(
                    dlc_page_link=context["url"],
                    ctx_cookies=ctx_cookies,
                    _ctx_session=challenger,
                )
                _runtime = {"status": result, "name": context["name"], "dlc": True}
                self.message_queue.put_nowait(_runtime)

    def just_do_it(self):
        """单步子任务 认领周免游戏"""
        # 检查并更新身份令牌
        if self.bricklayer.cookie_manager.refresh_ctx_cookies(
            _ctx_session=self.challenger
        ):
            # 读取有效的身份令牌
            ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

            # 扫描商城促销活动，返回“0折”商品的名称与商城链接
            limited_free_game_objs = self.explorer.get_the_absolute_free_game(
                ctx_cookies, _ctx_session=self.challenger
            )

            # 释放 Claimer 认领周免游戏
            urls = limited_free_game_objs["urls"]
            self.claim_free_game(
                challenger=self.challenger,
                ctx_cookies=ctx_cookies,
                game_objs=limited_free_game_objs,
                urls=urls,
            )

            # 释放 Claimer 认领游戏DLC
            self.claim_free_dlc(challenger=self.challenger, ctx_cookies=ctx_cookies)


class UnrealClaimerInstance(ClaimerInstance):
    """虚幻商城月供砖家"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False):
        super().__init__(silence=silence, log_ignore=log_ignore)

        self.bricklayer = UnrealClaimer(silence=silence)

    def just_do_it(self):
        """虚幻商城月供砖家"""
        # 检查并更新身份令牌
        if self.bricklayer.cookie_manager.refresh_ctx_cookies(
            _ctx_session=self.challenger
        ):
            # 读取有效的身份令牌
            ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

            # 释放 Claimer 认领免费内容
            self.bricklayer.get_free_resource(
                ctx=self.challenger, ctx_cookies=ctx_cookies
            )

            # 检查运行结果
            details = self.bricklayer.get_claimer_response(ctx_cookies)
            for detail in details:
                self.message_queue.put_nowait(detail)
