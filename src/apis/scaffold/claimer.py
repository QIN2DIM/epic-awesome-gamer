# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing

from services.deploy import ClaimerScheduler


def deploy(unreal: typing.Optional[bool] = False):
    """在微小容器中部署 `claim` 定时调度任务"""
    ClaimerScheduler(silence=True, unreal=unreal).deploy_on_vps()


def run(
    silence: typing.Optional[bool] = None,
    log_ignore: typing.Optional[bool] = None,
    unreal: typing.Optional[bool] = False,
):
    """运行 `claim` 单步子任务，认领周免游戏"""
    ClaimerScheduler(silence=silence, unreal=unreal).job_loop_claim(log_ignore)
