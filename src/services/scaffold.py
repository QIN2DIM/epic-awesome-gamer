# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import os
from typing import Literal

from loguru import logger


class Scaffold:
    """系统脚手架 顶级接口指令"""

    @staticmethod
    def install(upgrade: bool | None = None):
        """下载运行依赖"""
        from settings import config
        import hcaptcha_challenger as solver

        os.system("playwright install firefox")
        os.system("playwright install-deps firefox")
        solver.set_reverse_proxy(config.cdn)
        solver.install(upgrade=upgrade)

    @staticmethod
    def get():
        """
        清空免费商店

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
        :return:
        """
        logger.success("DONE [ScaffoldGet] 任务退出", reason="NotImplemented")

    @staticmethod
    def claim(mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"] = "epic-games"):
        """
        认领周免游戏，优雅地


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
        :return:
        """
        logger.info("Pass task", reason="NotImplemented")

    @staticmethod
    def log(start: bool | None = False):
        """
        显示最近一次的运行日志
        :param start: Default False. 自动打开日志目录（linux无效，仅会显示文件目录）。
        :return:
        """
