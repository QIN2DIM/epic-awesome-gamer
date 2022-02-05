# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

import apprise
from apscheduler.schedulers.blocking import BlockingScheduler

from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger, MESSAGE_PUSHER_SETTINGS
from services.utils import ToolBox


class ClaimerScheduler:
    def __init__(self, silence: Optional[bool] = None):

        self.action_name = "AwesomeScheduler"
        self.SPAWN_TIME = "spawn_time"

        # 服务注册
        self.scheduler = BlockingScheduler()
        self.bricklayer = Bricklayer(silence=silence)
        self.explorer = Explorer(silence=silence)
        self.logger = logger

    def deploy_jobs(self):
        """
        https://crontab.guru/
        schedule:
            - cron: "5 4 * * 5"
            - cron: "3 2 * * 6"
        :return:
        """

    def start(self):
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            self.scheduler.shutdown(wait=False)
            self.logger.debug(ToolBox.runtime_report(
                motive="EXITS",
                action_name=self.action_name,
                message="Received keyboard interrupt signal."
            ))

    def job_loop_claim(self):

        def _release_power(urls: Optional[list] = None):
            if not urls:
                self.logger.debug(ToolBox.runtime_report(
                    motive="SKIP",
                    action_name=self.action_name,
                    message=f"🛴 当前玩家暂无待认领的周免游戏。"
                ))
                return

            # 优先处理常规情况 urls.__len__() == 1
            for url in urls:
                self.logger.debug(ToolBox.runtime_report(
                    motive="STARTUP",
                    action_name="ScaffoldClaim",
                    message="🍜 正在为玩家领取周免游戏",
                    game=f"『{limited_free_game_objs[url]}』"
                ))
                response = self.bricklayer.get_free_game(
                    page_link=url,
                    ctx_cookies=ctx_cookies,
                    challenge=True
                )

                # 编制运行缓存 用于生成业务报告
                _runtime = {
                    self.SPAWN_TIME: ToolBox.date_format_now(),
                    "flag": "💰" if response else "🚫",
                    "name": limited_free_game_objs[url],
                }
                inline_docker.append(_runtime)

        # 更新身份令牌
        if not self.bricklayer.cookie_manager.refresh_ctx_cookies(verify=True):
            return
        ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

        # 扫描商城促销活动，返回“0折”商品的名称与商城链接
        limited_free_game_objs = self.explorer.get_the_limited_free_game(ctx_cookies)

        # 初始化内联数据容器 临时存储运行缓存
        inline_docker = []

        # 释放 Claimer 认领周免游戏
        _release_power(limited_free_game_objs["urls"])

        # 缓存卸载 发送运行日志
        self.push(inline_docker)

    def push(self, inline_docker: list, pusher_settings: Optional[dict] = None):
        """

        :param inline_docker:
        :param pusher_settings:
        :return:
        """

        """
        [♻]参数过滤
        _______________
        """
        if pusher_settings is None:
            pusher_settings = MESSAGE_PUSHER_SETTINGS
        if not pusher_settings["enable"]:
            return

        """
        [📧]消息推送
        _______________
        """
        # 组织推送模版
        _inline_textbox = [f"当前玩家：{ToolBox.secret_email(self.bricklayer.email)}", ]
        _inline_textbox += ["运行日志".center(20, "-"), ]
        if not inline_docker:
            _inline_textbox += [f"[{ToolBox.date_format_now()}] 🛴 暂无可领取的周免游戏", ]
        else:
            _inline_textbox += [f"[{game_obj[self.SPAWN_TIME]}] {game_obj['flag']} {game_obj['name']}"
                                for game_obj in inline_docker]
        _inline_textbox += ["生命周期统计".center(20, "-"), f"total:{inline_docker.__len__()}"]

        # 注册 Apprise 消息推送框架
        active_pusher = pusher_settings["pusher"]
        surprise = apprise.Apprise()
        for server in active_pusher.values():
            surprise.add(server)

        # 发送模版消息
        surprise.notify(
            body="\n".join(_inline_textbox),
            title="EpicAwesomeGamer 运行报告",
        )

        self.logger.success(ToolBox.runtime_report(
            motive="Notify",
            action_name=self.action_name,
            message="消息推送完毕",
            active_pusher=[i[0] for i in active_pusher.items() if i[-1]]
        ))
