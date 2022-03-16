# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
from datetime import datetime, timedelta
from typing import Optional

import apprise
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger, MESSAGE_PUSHER_SETTINGS
from services.utils import ToolBox, get_challenge_ctx


class ClaimerScheduler:
    """系统任务调度器"""

    SPAWN_TIME = "spawn_time"

    def __init__(self, silence: Optional[bool] = None):
        self.action_name = "AwesomeScheduler"
        self.end_date = datetime.now(pytz.timezone("Asia/Shanghai")) + timedelta(days=180)
        self.silence = silence
        # 服务注册
        self.scheduler = BlockingScheduler()
        self.bricklayer = Bricklayer(silence=silence)
        self.explorer = Explorer(silence=silence)
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
        _inline_textbox = [f"当前玩家：{ToolBox.secret_email(self.bricklayer.email)}"]
        _inline_textbox += ["运行日志".center(20, "-")]
        if not inline_docker:
            _inline_textbox += [f"[{ToolBox.date_format_now()}] 🛴 暂无待认领的周免游戏"]
        else:
            _inline_textbox += [
                f"[{game_obj[self.SPAWN_TIME]}] {game_obj['name']} {game_obj['status']}"
                for game_obj in inline_docker
            ]
        _inline_textbox += ["生命周期统计".center(20, "-"), f"total:{inline_docker.__len__()}"]

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
        """单步子任务 认领周免游戏"""

        def _release_power(urls: Optional[list] = None):
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
                        game=f"『{limited_free_game_objs[url]}』",
                    )
                )

                # 反复生产挑战者领取周免游戏
                self.bricklayer.get_free_game(
                    page_link=url, ctx_cookies=ctx_cookies, _ctx_session=challenger
                )
                # 编制运行缓存 用于生成业务报告
                _runtime = {
                    self.SPAWN_TIME: ToolBox.date_format_now(),
                    "status": self.bricklayer.result,
                    "name": limited_free_game_objs[url],
                }
                inline_docker.append(_runtime)

        # 标记运行时刻
        if self.scheduler.running:
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="JOB",
                    action_name=self.action_name,
                    message="定时任务启动",
                    job="claim",
                )
            )

        # 初始化内联数据容器 临时存储运行缓存
        inline_docker = []

        challenger = get_challenge_ctx(silence=self.silence)
        try:
            # 更新身份令牌
            if not self.bricklayer.cookie_manager.refresh_ctx_cookies(
                _ctx_session=challenger
            ):
                return
            ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

            # 扫描商城促销活动，返回“0折”商品的名称与商城链接
            limited_free_game_objs = self.explorer.get_the_absolute_free_game(
                ctx_cookies, _ctx_session=challenger
            )

            # 释放 Claimer 认领周免游戏
            _release_power(limited_free_game_objs["urls"])
        finally:
            challenger.quit()

        # 缓存卸载 发送运行日志
        self._push(inline_docker)
