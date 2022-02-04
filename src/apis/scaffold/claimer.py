# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.deploy import AwesomeScheduler

SILENCE = False


def deploy():
    pass


def run():
    AwesomeScheduler(silence=SILENCE).job_loop_claim()
