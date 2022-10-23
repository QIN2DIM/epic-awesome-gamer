# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing


class Explorer(Exception):
    def __init__(
        self,
        msg: typing.Optional[str] = None,
        stacktrace: typing.Optional[typing.Sequence[str]] = None,
    ):
        self.msg = msg
        self.stacktrace = stacktrace
        super().__init__()

    def __str__(self) -> str:
        exception_msg = f"Message: {self.msg}\n"
        if self.stacktrace:
            stacktrace = "\n".join(self.stacktrace)
            exception_msg += f"Stacktrace:\n{stacktrace}"
        return exception_msg
