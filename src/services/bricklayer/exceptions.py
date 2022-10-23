# -*- coding: utf-8 -*-
# Time       : 2022/1/17 15:20
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional, Sequence


class AwesomeException(Exception):
    def __init__(self, msg: Optional[str] = None, stacktrace: Optional[Sequence[str]] = None):
        self.msg = msg
        self.stacktrace = stacktrace
        super().__init__()

    def __str__(self) -> str:
        exception_msg = f"Message: {self.msg}\n"
        if self.stacktrace:
            stacktrace = "\n".join(self.stacktrace)
            exception_msg += f"Stacktrace:\n{stacktrace}"
        return exception_msg


class AuthException(AwesomeException):
    """身份认证出现问题时抛出，例如遭遇插入到 hcaptcha 之后的 2FA 身份验证"""


class AuthMFA(AuthException):
    """認證失敗，不支持 2FA 雙重認證"""


class LoginException(AuthException):
    """認證失敗，賬號或密碼錯誤"""


class AuthUnknownException(AuthException):
    def __init__(self, msg=None, stacktrace=None):
        super().__init__(msg, stacktrace)
        self.__doc__ = None

    def report(self, msg):
        self.__doc__ = msg


class UnableToGet(AwesomeException):
    """不可抗力因素，游戏无法获取"""
