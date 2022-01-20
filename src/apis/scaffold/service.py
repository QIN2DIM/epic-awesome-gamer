# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.deploy import AwesomeScheduler
from services.settings import (
    SCHEDULER_SETTINGS, logger
)
from services.utils import ToolBox


class SystemCrontab:
    """部署定时任务"""

    def __init__(self, **optional):
        self.ACTION_NAME = "SystemService"

        self.scheduler_settings = self._calibrate(**optional)

    def _calibrate(self, **optional):
        scheduler_settings: dict = SCHEDULER_SETTINGS
        task_stack = ["explorer", "bricklayer"]

        for lok in task_stack:
            if not scheduler_settings.get(lok):
                scheduler_settings[lok] = {}
            if optional.get(lok) is not None:
                scheduler_settings[lok]["enable"] = optional.get(lok)

        scheduler_settings["explorer"]["interval"] = max(120, scheduler_settings["explorer"].get("interval", 120))
        scheduler_settings["bricklayer"]["interval"] = max(600, scheduler_settings["bricklayer"].get("interval", 600))

        for lok in task_stack:
            interval = scheduler_settings[lok]["interval"]
            logger.info(ToolBox.runtime_report(
                motive="JOB",
                action_name=f"{self.ACTION_NAME}|Configuration",
                message="Interval--({})--{}s".format(lok, interval)
            ))

        return scheduler_settings

    def service_scheduler(self):
        # 实例化子模块任务
        collector = AwesomeScheduler(job_settings={
            "interval_explorer": self.scheduler_settings["explorer"]["interval"],
            "interval_bricklayer": self.scheduler_settings["bricklayer"]["interval"],
        })

        # 自适应部署子模块任务
        collector.deploy_jobs(
            available_explorer=self.scheduler_settings["explorer"]["enable"],
            available_bricklayer=self.scheduler_settings["bricklayer"]["enable"]
        )
