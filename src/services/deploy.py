# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from apscheduler.schedulers.blocking import BlockingScheduler

from services.settings import logger
from services.utils import ToolBox


class AwesomeScheduler:
    def __init__(self, job_settings: dict):
        self.job_settings = job_settings

        self.scheduler = BlockingScheduler()
        self.scheduler_name = "AwesomeScheduler"

    def deploy_jobs(self, available_explorer=True, available_bricklayer=True):
        if available_explorer:
            pass
        if available_bricklayer:
            pass

        if any((available_explorer, available_bricklayer)):
            self.start()

    def start(self):
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            self.scheduler.shutdown(wait=False)
            logger.debug(ToolBox.runtime_report(
                motive="EXITS",
                action_name=self.scheduler_name,
                message="Received keyboard interrupt signal."
            ))

    def _deploy_explorer(self):
        pass

    def _deploy_bricklayer(self):
        pass
