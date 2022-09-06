# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from loguru import logger

from apis.scaffold import get, challenge, install, claimer, console


class Scaffold:
    """系统脚手架 顶级接口指令"""

    DEFAULT_YOLO_MODEL = "yolov6t"

    @staticmethod
    def install(onnx_prefix: Optional[str] = None, upgrade: Optional[bool] = None):
        """下载运行依赖"""
        onnx_prefix = Scaffold.DEFAULT_YOLO_MODEL if onnx_prefix is None else onnx_prefix
        install.do(yolo_onnx_prefix=onnx_prefix, upgrade=upgrade)

    @staticmethod
    def test():
        """检查挑战者驱动版本是否适配"""
        install.test()

    @staticmethod
    def challenge(silence: Optional[bool] = True):
        """

        Introduction
        --------

        正面硬刚人机挑战，为当前账号获取有效的身份令牌。

        - 请确保你已在 ``config.yaml`` 中配置了正确的账号信息。
        - 更新后的身份令牌存储在 ``/src/database/cookies/user_cookies.txt``

        Tips
        --------

        ``challenge`` **不会强制激活人机验证**。获取有效的身份令牌才是目的，不要徒增功耗。

        :param silence: 默认True。是否静默启动浏览器。除非你想观赏系统的作业流程，否则别徒增功耗。
          该项在 Linux 上始终为True，无法手动指定。
        :return:
        """
        challenge.run(silence=silence)

    @staticmethod
    def get(
        debug: Optional[bool] = None,
        cache: Optional[bool] = True,
        dlc: Optional[bool] = False,
        unreal: Optional[bool] = False,
        silence: Optional[bool] = True,
        dev: Optional[str] = None,
    ):
        """

        Introduction
        -------

        「我可以不玩但不能没有。」—— 鲁·克莱摩·迅

        - **搬空免费商店**

          这是个趣味性和观赏性都拉满的一次性任务。

          系统将发起 4 协程并发的驱动任务，为你节省扫描时间。

        - **六根清净方为道，退步原来是向前**

          显然地，这是一项对操作系统内存和网络 I/O 要求都不低的任务，

          如果你嫌这五六十款（不同地区权限不同）多余的常驻免费游戏会影响你翻找游戏库的效率，请速速退朝。

        - **跳过周免游戏**

          ``get`` 启动标准上下文执行任务，其并不足以应付隐藏在订单中的人机挑战。

          因此，``get`` 会自动跳过未认领的周免游戏。请使用生产效率更高的 ``claim`` 指令认领周免游戏。

        Advanced
        ---------

        此指令会将免费商城数据存储在 ``src/database/explorer``，

        存储内容与当前上下文身份令牌有关（不同地区权限不同）。

        :param dev:
        :param unreal: 默认False，与 ``dlc`` 只能同时生效一个。清扫虚幻商店所有可领取的免费内容。
        :param silence: 默认True。是否静默启动浏览器。除非你想观赏系统的作业流程，否则别徒增功耗。
          该项在 Linux 上始终为True，无法手动指定。
        :param dlc: 默认False，与 ``unreal`` 只能同时生效一个。
            清扫 DLC（游戏附加内容）此模式清扫所有免费 DLC，不包括付费游戏的免费DLC。
        :param cache: 默认True。优先读取本地的商城缓存数据。本地不存在或缓存过时则自动更新。
        :param debug: 默认False。显示栈追踪日志信息。
        :return:
        """
        if dlc is True:
            category = "dlc"
        elif unreal is True:
            category = "unreal"
        else:
            category = "game"
        logger.critical(
            "The scaffolding command `get` is not open for use at this time, and related tasks will be skipped."
        )
        if dev == "chichao":
            get.join(debug=debug, cache=cache, category=category, silence=silence)

    @staticmethod
    def claim(
        silence: Optional[bool] = True,
        ignore: Optional[bool] = False,
        unreal: Optional[bool] = False,
    ):
        """
        Introduction
        --------

        **认领周免游戏，优雅地**
          ``claim`` 做的事情非常简单：

          1.获取本周促销数据；

          2.分析是否有待认领的周免游戏；

          3.激活驱动领取未在库游戏。

          值得一提的是，第 **3** 步之前都是简单的并发网络请求行为，只有识别出未在库游戏时才会启动浏览器。
          因此，``claim`` 作为前置任务启动时，执行效率非常高。

        Advanced
        --------

        **基于 apprise 实现的消息推送模型**
          ``claim`` 在上述业务结束后将根据当前的 ``pusher`` 参数推送追踪日志。
          需要注意的是，未配置或配置错误均不会发送消息。

        :param silence: 默认True。是否静默启动浏览器。除非你想观赏系统的作业流程，否则别徒增功耗。
          该项在 Linux 上始终为True，无法手动指定。
        :param ignore: 默认False。忽略已在库的推送数据。若所有周免内容均已在库，跳过消息推送。
          该参数为开发者设计，部分推送渠道的试用账号按条数收费或每日限量收发，使用此参数可在重复
          任务时节约资源。
        :param unreal: 默认False。虚幻商城月供砖家。将任务句柄由<游戏商店>切换至<虚幻商店>，
          业务内容保持一致。脚手架指令 unreal 与此入口意义相同。
        :return:
        """
        install.do()
        claimer.run(silence=silence, log_ignore=ignore, unreal=unreal)

    @staticmethod
    def unreal(silence: Optional[bool] = True, ignore: Optional[bool] = False):
        """虚幻商城月供砖家 贤者专用"""
        Scaffold.claim(silence=silence, ignore=ignore, unreal=True)

    @staticmethod
    def deploy(unreal: Optional[bool] = False):
        """
        部署系统定时任务。

        :param unreal: 默认False。虚幻商城月供砖家。将任务句柄由<游戏商店>切换至<虚幻商店>，
          业务内容保持一致。
        :return:
        """
        claimer.deploy(unreal=unreal)

    @staticmethod
    def log(start: Optional[bool] = False):
        """
        显示最近一次的运行日志。
        :param start: Default False. 自动打开日志目录（linux无效，仅会显示文件目录）。
        :return:
        """
        console.get_logger(start=start)
