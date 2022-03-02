# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional, Sequence


class Explorer(Exception):
    def __init__(
        self, msg: Optional[str] = None, stacktrace: Optional[Sequence[str]] = None
    ):
        self.msg = msg
        self.stacktrace = stacktrace
        super().__init__()

    def __str__(self) -> str:
        exception_msg = "Message: {}\n".format(self.msg)
        if self.stacktrace:
            stacktrace = "\n".join(self.stacktrace)
            exception_msg += "Stacktrace:\n{}".format(stacktrace)
        return exception_msg


class DiscoveryTimeoutException(Explorer):
    """未能在规定时间内为指定玩家搜索免费游戏"""
