from typing import Optional, Sequence


class ArmorException(Exception):
    def __init__(
        self, msg: Optional[str] = None, stacktrace: Optional[Sequence[str]] = None
    ):
        self.msg = msg
        self.stacktrace = stacktrace
        super(ArmorException, self).__init__()

    def __str__(self) -> str:
        exception_msg = "Message: {}\n".format(self.msg)
        if self.stacktrace:
            stacktrace = "\n".join(self.stacktrace)
            exception_msg += "Stacktrace:\n{}".format(stacktrace)
        return exception_msg


class ChallengeException(ArmorException):
    pass


class ChallengeReset(ChallengeException):
    """挑战失败，需要重试"""

    pass


class LoadImageTimeout(ChallengeException):
    """加载挑战图片超时"""

    pass


class LabelNotFoundException(ChallengeException):
    """获取到空的图像标签名"""

    pass
