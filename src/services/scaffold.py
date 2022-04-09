# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from apis.scaffold import get, challenge, install, claimer


class Scaffold:
    """系统脚手架 顶级接口指令"""

    @staticmethod
    def install(onnx_prefix: Optional[str] = None):
        """下载运行依赖"""
        install.run(onnx_prefix=onnx_prefix)

    @staticmethod
    def test():
        """检查挑战者驱动版本是否适配"""
        install.test()

    @staticmethod
    def challenge(silence: Optional[bool] = True):
        """
        正面硬刚人机挑战，为当前账号获取有效的身份令牌。

        ## Intro

        - 请确保你已在 `config.yaml` 中配置了正确的账号信息。
        - 更新后的 cookie 存储在 `/src/database/cookies/user_cookies.txt` 文件中

        ## Tips

        - 本指令并不会强制激活人机验证。硬刚人机挑战不是目的，获取到有效的身份令牌才是目的，不要徒增功耗。
        - 也即，如果当前缓存的身份令牌还未失效，挑战跳过。

        :param silence: (Default: True) IF False: 将在图形化系统中显式启动浏览器，演示人机挑战的执行过程。
        :return:
        """
        challenge.run(silence=silence)

    @staticmethod
    def get(
        debug: Optional[bool] = None,
        cache: Optional[bool] = True,
        dlc: Optional[bool] = False,
    ):
        """
        「我可以不玩但不能没有。」—— 鲁·克莱摩·迅

        ## Intro

        - `get` 只做一件事，搬空免费商店！

        - 这是个趣味性和观赏性都拉满的一次性任务。系统会根据你的设备性能发起最高 4 协程并发的驱动任务，为你节省扫荡时间。

        - 显然地，这是一项对操作系统内存和网络I/O要求都不低的任务，如果你嫌这五六十款（不同地区权限不同）
        多余的常驻免费游戏会影响你翻找游戏库的效率，请速速退朝。

        - `get` 指令启动标准上下文执行任务，其并不足以应付隐藏在订单中的人机挑战。因此，`get` 指令会自动跳过未认领的周免游戏。
        请使用生产效率更高的 `claim` 指令认领周免游戏。

        ## Local Static CacheFile

        此指令会将免费商城数据存储在 `src/database/explorer` 目录下。存储内容与当前上下文身份令牌有关（不同地区权限不同）

        ## Contributes

        - 若运行出现意料之外的报错，请运行 debug 模式，留意 Exception 信息，并将完整的栈追踪信息提交至 `issues` ，不胜感激！
        -  https://github.com/QIN2DIM/epic-awesome-gamer

        :param dlc: 清扫 DLC（游戏附加内容）。
            此模式清扫所有免费 DLC，也即付费游戏/周免游戏/常驻免费游戏的免费附加内容。
            ~~应该没人这么无聊吧~~
        :param cache: 使用商城缓存数据
        :param debug: 显示栈追踪日志信息
        :return:
        """
        category = "dlc" if bool(dlc) else "game"
        get.join(trace=debug, cache=cache, category=category)

    @staticmethod
    def claim(
        silence: Optional[bool] = True,
        ignore: Optional[bool] = False,
        unreal: Optional[bool] = False,
    ):
        """
        认领周免游戏。

        ## Intro

        `claim` 做的事非常简单，获取本周促销数据，分析是否有待认领的周免游戏，根据分析结果执行相关任务。

        `claim` 是系统级指令 `deploy` 的单步子任务，在上述业务结束后，会根据你配置的 `pusher` 推送追踪日志（若配置无效则不发）。

        :param unreal: 虚幻商城月供砖家
        :param silence:
        :param ignore: 忽略已在库的推送数据。
        :return:
        """
        claimer.run(silence=silence, log_ignore=ignore, unreal=unreal)

    @staticmethod
    def unreal(silence: Optional[bool] = True, ignore: Optional[bool] = False):
        """虚幻商城月供砖家 贤者专用"""
        Scaffold.claim(silence=silence, ignore=ignore, unreal=True)

    @staticmethod
    def deploy(platform: Optional[str] = None, unreal: Optional[bool] = False):
        """
        部署系统定时任务。

        :param unreal: 虚幻商城月供砖家
        :param platform: 可选项 [vps serverless qing-long]
        :return:
        """
        claimer.deploy(platform, unreal=unreal)
