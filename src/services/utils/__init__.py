# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import sys
import typing

from ._undetected_chromedriver import Chrome as Challenger
from .toolbox.pusher import MessagePusher
from .toolbox.toolbox import ToolBox
from .toolbox.toolbox import get_ctx, DriverWrapper

__all__ = ["MessagePusher", "ToolBox", "get_challenge_ctx", "get_ctx", "Challenger"]


def get_challenge_ctx(
    silence: typing.Optional[bool] = None, user_data_dir: typing.Optional[str] = None
) -> Challenger:
    """挑战者驱动 用于处理人机挑战"""
    driver_wrapper = DriverWrapper()
    options = driver_wrapper.options

    silence = True if silence is None or "linux" in sys.platform else silence

    # Create challenger
    # logging.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "🎮 激活挑战者上下文"))
    return Challenger(
        headless=silence,
        options=options,
        driver_executable_path=driver_wrapper.path,
        user_data_dir=user_data_dir,
    )
