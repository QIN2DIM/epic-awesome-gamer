# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from selenium.common.exceptions import WebDriverException

from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger
from services.utils import (
    CoroutineSpeedup,
    ToolBox
)

SILENCE = True

bricklayer = Bricklayer(silence=SILENCE)
explorer = Explorer(silence=SILENCE)


class SpawnBooster(CoroutineSpeedup):
    def __init__(self, docker, ctx_cookies, power: Optional[int] = None, debug: Optional[bool] = None):
        super(SpawnBooster, self).__init__(docker=docker, power=power)

        self.debug = False if debug is None else debug
        self.power = min(4, 4 if power is None else power)
        self.action_name = "SpawnBooster"

        self.ctx_cookies = ctx_cookies

    def control_driver(self, url, *args, **kwargs):
        # 运行前置检查
        response = explorer.game_manager.is_my_game(ctx_cookies=self.ctx_cookies, page_link=url)

        # 启动 Bricklayer，获取免费游戏
        if response.get("status") is False:
            logger.debug(ToolBox.runtime_report(
                motive="BUILD",
                action_name=self.action_name,
                message="🛒 正在为玩家领取免费游戏",
                progress=f"[{self.progress()}]",
                url=url
            ))

            try:
                bricklayer.get_free_game(page_link=url, ctx_cookies=self.ctx_cookies, refresh=False)
            except WebDriverException as e:
                # self.done.put_nowait(url)
                if self.debug:
                    logger.exception(e)
                logger.error(ToolBox.runtime_report(
                    motive="QUIT",
                    action_name="SpawnBooster",
                    message="未知错误",
                    progress=f"[{self.progress()}]",
                    url=url
                ))

    def killer(self):
        logger.success(ToolBox.runtime_report(
            motive="OVER",
            action_name=self.action_name,
            message="✔ 任务队列已清空"
        ))


def join(trace: bool = False):
    """
    科技改变生活，一键操作，将免费商城搬空！

    :param trace:
    :return:
    """
    logger.info(ToolBox.runtime_report(
        motive="STARTUP",
        action_name="ScaffoldGet",
        message="🔨 正在为玩家领取免费游戏"
    ))

    """
    [🔨] 读取有效的身份令牌
    _______________
    - 必要时激活人机挑战
    """
    if not bricklayer.cookie_manager.refresh_ctx_cookies(verify=True):
        return
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    """
    [🔨] 更新商城的免费游戏
    _______________
    """
    urls = explorer.game_manager.load_game_objs(only_url=True)
    if not urls:
        urls = explorer.discovery_free_games(ctx_cookies=ctx_cookies, cover=True)

    """
    [🔨] 启动 Bricklayer，获取免费游戏
    _______________
    - 启动一轮协程任务，执行效率受限于本地网络带宽，若首轮报错频发请手动调低 `power` 参数。
    - 如果在命令行操作系统上运行本指令，执行效率受限于硬件性能。
    """
    booster = SpawnBooster(ctx_cookies=ctx_cookies, docker=urls, power=4, debug=trace)
    booster.go()


def special(special_link: str):
    if not special_link.startswith("https://www.epicgames.com/store/zh-CN"):
        logger.critical(ToolBox.runtime_report(
            motive="STARTUP",
            action_name="ScaffoldGet",
            message="链接不合法"
        ))
        return
    logger.info(ToolBox.runtime_report(
        motive="STARTUP",
        action_name="ScaffoldGet",
        message="🎯 正在为玩家领取指定游戏"
    ))

    if not bricklayer.cookie_manager.refresh_ctx_cookies(verify=True):
        return

    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    bricklayer.get_free_game(
        page_link=special_link,
        ctx_cookies=ctx_cookies,
        challenge=True
    )
