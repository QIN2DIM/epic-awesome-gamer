# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from services.deploy import ClaimerScheduler
from services.settings import logger


@logger.catch()
def deploy(unreal: Optional[bool] = False):
    """在微小容器中部署 `claim` 定时调度任务"""
    ClaimerScheduler(silence=True, unreal=unreal).deploy_on_vps()


@logger.catch()
def run(
    silence: Optional[bool] = None,
    log_ignore: Optional[bool] = None,
    unreal: Optional[bool] = False,
):
    """运行 `claim` 单步子任务，认领周免游戏"""
    ClaimerScheduler(silence=silence, unreal=unreal).job_loop_claim(log_ignore)
