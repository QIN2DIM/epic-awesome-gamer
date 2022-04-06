# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from services.deploy import ClaimerScheduler, ClaimerInstance, UnrealClaimerInstance
from services.settings import logger


@logger.catch()
def deploy(platform: Optional[str] = None, unreal: Optional[bool] = False):
    """在微小容器中部署 `claim` 定时调度任务"""
    ClaimerScheduler(silence=True, unreal=unreal).deploy_jobs(platform)


@logger.catch()
def run(
    silence: Optional[bool] = None,
    log_ignore: Optional[bool] = None,
    unreal: Optional[bool] = False,
):
    """运行 `claim` 单步子任务，认领周免游戏"""
    if not unreal:
        with ClaimerInstance(silence=silence, log_ignore=log_ignore) as claimer:
            claimer.just_do_it()
    else:
        with UnrealClaimerInstance(silence=silence, log_ignore=log_ignore) as claimer:
            claimer.just_do_it()
