# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing

from undetected_chromedriver import Chrome as Challenger

from .pusher import MessagePusher
from .toolbox import DriverWrapper, ToolBox, get_ctx

__all__ = ["MessagePusher", "ToolBox", "get_challenge_ctx", "get_ctx", "Challenger"]


def get_challenge_ctx(silence: typing.Optional[bool] = None) -> Challenger:
    """挑战者驱动 用于处理人机挑战"""
    driver_wrapper = DriverWrapper(silence=silence)
    options = driver_wrapper.options

    # Create challenger
    # logging.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "🎮 激活挑战者上下文"))
    return Challenger(options=options, driver_executable_path=driver_wrapper.path)
