# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import time
from itertools import zip_longest
from typing import Optional

import gevent
from gevent.queue import Queue
from selenium.common.exceptions import WebDriverException

from services.bricklayer import GameClaimer
from services.bricklayer.exceptions import PaymentBlockedWarning
from services.explorer import Explorer
from services.settings import logger
from services.utils import ToolBox, get_ctx


class SteelTorrent:
    """▶ 播放『钢铁洪流进行曲』"""

    # 最佳实践，不可改动
    POWER = 2 if os.cpu_count() < 2 else 4

    def __init__(
        self, ctx_cookies, category, silence: Optional[bool] = None, debug: Optional[bool] = None
    ):
        self.ctx_cookies = ctx_cookies
        self.category = category
        self.silence = silence
        self.debug = False if debug is None else debug

        self.action_name = "SteelTorrent"

        # 待领取的常驻免费游戏实例
        self.pending_jobs = Queue()
        # 已处理的免费游戏实例(打上标签)
        self.done_jobs = Queue()
        # 维护一个受控的 WebDriver 任务队列
        self.pending_workers = Queue(self.POWER + 1)

        # 服务注册
        self.bricklayer = GameClaimer(silence=self.silence, claim_mode=GameClaimer.CLAIM_MODE_GET)
        self.explorer = Explorer(silence=self.silence)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        while not self.pending_workers.empty():
            ctx_session = self.pending_workers.get()
            try:
                ctx_session.quit()
            except (AttributeError, WebDriverException):
                pass

        logger.success(
            ToolBox.runtime_report(motive="OVER", action_name=self.action_name, message="✔ 任务队列已清空")
        )

    def _require_worker(self) -> get_ctx:
        """获取驱动上下文"""
        if not self.pending_workers.empty():
            return self.pending_workers.get_nowait()
        return get_ctx(self.silence)

    def _release_worker(self, worker):
        self.pending_workers.put(worker)

    def _offload(self, game_obj=None):
        if game_obj:
            _game_objs = [game_obj]
        else:
            _game_objs = []
            while not self.done_jobs.empty():
                _game_objs.append(self.done_jobs.get())
        self.explorer.game_manager.save_game_objs(_game_objs, category=self.category, runtime=True)

    def in_library(self, job: dict, review=None) -> Optional[bool]:
        """识别游戏在库状态"""
        response = self.explorer.game_manager.is_my_game(
            ctx_cookies=self.ctx_cookies, page_link=job["url"]
        )

        # 识别未在库的常驻周免游戏
        if response.get("status") is False and response.get("assert") not in [
            "AjaxLoadingReject",
            "AssertObjectNotFound",
        ]:
            return False
        if response.get("status") is True or review:
            job["in_library"] = True
            self.done_jobs.put_nowait(job)
        return True

    def perform(self, job):
        name, url = job["name"], job["url"]

        # 运行前置检查
        if self.in_library(job):
            return

        logger.debug(
            ToolBox.runtime_report(
                motive="BUILD",
                action_name=self.action_name,
                message="🛒 发现待领取的免费游戏",
                pending_jobs=f"[{self.pending_jobs.qsize()}]",
                name=name,
                url=url,
            )
        )

        # 启动 Bricklayer 获取免费游戏
        ctx_session = self._require_worker()
        try:
            self.bricklayer.claim_stabilizer(
                page_link=url,
                ctx_cookies=self.ctx_cookies,
                ctx_session=ctx_session,
                get_blocked_warning=True,
            )
        except PaymentBlockedWarning:
            job["blocked"] = True
            self.done_jobs.put_nowait(job)
        except WebDriverException as error:
            if self.debug:
                logger.exception(error)
            else:
                logger.error(
                    ToolBox.runtime_report(
                        motive="QUIT",
                        action_name="SpawnBooster",
                        message="未知错误",
                        pending_jobs=f"[{self.pending_jobs.qsize()}]",
                        url=url,
                    )
                )
        finally:
            self._release_worker(ctx_session)
            self.in_library(job)

    def kernel(self):
        while not self.pending_jobs.empty():
            context = self.pending_jobs.get_nowait()
            self.perform(context)

    def advance(self, jobs):
        for job in jobs:
            self.pending_jobs.put(job)

        # 弹出空载任务
        if self.pending_jobs.qsize() == 0:
            return

        # 启动分流核心
        kernel_matrix = []
        for _ in range(self.POWER):
            task = gevent.spawn(self.kernel)
            kernel_matrix.append(task)
        gevent.joinall(kernel_matrix)

        # 缓存卸载
        self._offload()


@logger.catch()
def join(
    debug: bool = False, cache: bool = True, category: str = "game", silence: Optional[bool] = True
):
    """
    一键搬空免费商店

    需要确保上下文身份令牌有效，可通过 `challenge` 脚手架强制刷新。
    :param silence:
    :param category:
    :param cache:
    :param debug:
    :return:
    """
    logger.info(
        ToolBox.runtime_report(motive="STARTUP", action_name="ScaffoldGet", message="🔨 正在为玩家领取免费资源")
    )

    # [🔨] 读取有效的身份令牌
    bricklayer = GameClaimer()
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()
    if not bricklayer.cookie_manager.is_available_cookie(ctx_cookies):
        logger.critical(
            ToolBox.runtime_report(
                motive="SKIP",
                action_name="ScaffoldGet",
                message="身份令牌不存在或失效，手动执行 `challenge` 指令更新身份令牌。",
            )
        )
        return

    # [🔨] 缓存免费商城数据
    explorer = Explorer()
    game_objs = explorer.game_manager.load_game_objs(category=category)
    # 缓存过期或强制更新
    if not cache or not game_objs:
        game_objs = explorer.discovery_free_games(
            ctx_cookies=ctx_cookies, category=category, silence=True
        )

    # [🔨] 分割进程池实例
    pending_jobs = [
        game for game in game_objs if not game["in_library"] and not game.get("blocked")
    ]
    if not pending_jobs:
        logger.success(
            ToolBox.runtime_report(
                motive="DONE",
                action_name="SteelTorrent",
                message="✔ 解锁成就：搬空免费商店",
                category=category,
            )
        )
        return

    # [🔨] 启动协同任务
    batch = 8
    random.shuffle(pending_jobs)
    with SteelTorrent(ctx_cookies, category, silence, debug) as steel_torrent:
        # 启动一轮协程任务，执行效率受限于本地网络带宽
        job_sequence = list(enumerate(zip_longest(*[iter(pending_jobs)] * batch)))
        for e, jobs in job_sequence:
            # 计算剩余任务数
            r = len(job_sequence[e:-1]) * batch + len([i for i in job_sequence[-1] if i])
            # 任务除杂
            jobs = [x for x in jobs if x]

            logger.debug(
                ToolBox.runtime_report(
                    motive="FLUSH",
                    action_name=steel_torrent.action_name,
                    message="获取分流任务",
                    epoch=f"[{e + 1}|{len(job_sequence)}]",
                    batch=len(jobs),
                    qsize=r,
                )
            )

            # ▶ 播放『钢铁洪流进行曲』
            steel_torrent.advance(jobs)

            if e != len(jobs) - 1:
                logger.debug(
                    ToolBox.runtime_report(
                        motive="SLEEP",
                        action_name=steel_torrent.action_name,
                        message="任務休眠",
                        sleep=f"{batch}s",
                    )
                )
                time.sleep(batch)
