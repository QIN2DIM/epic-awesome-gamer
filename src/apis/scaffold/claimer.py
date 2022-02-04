# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.deploy import ClaimerScheduler

SILENCE = True


def deploy():
    pass


def run():
    ClaimerScheduler(silence=SILENCE).job_loop_claim()
