# -*- coding: utf-8 -*-
# Time       : 2022/1/20 16:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from webdriver_manager.chrome import ChromeDriverManager

from services.settings import DIR_MODEL, logger
from services.utils import YOLO, CoroutineSpeedup, ToolBox
from services.utils import get_challenge_ctx


def _download_model():
    """
    下载 YOLOv4 目标检测模型

    :return:
    """
    logger.debug("下载 YOLOv4 目标检测模型...")
    YOLO(dir_model=DIR_MODEL).download_model()


def _download_driver():
    """
    下载浏览器驱动。

    :return:
    """
    logger.debug("适配 ChromeDriver...")
    ChromeDriverManager(version="latest").install()


class PerformanceReleaser(CoroutineSpeedup):
    """协程助推器 并发执行片段代码"""

    def __init__(self, docker, power=None):
        super().__init__(docker=docker, power=power)

    @logger.catch()
    def control_driver(self, task, *args, **kwargs):
        task()


def run():
    """
    下载项目运行所需的各项依赖。

    :return:
    """
    logger.debug(
        ToolBox.runtime_report(
            motive="BUILD",
            action_name="ScaffoldInstaller",
            message="正在下载系统依赖",
        )
    )

    PerformanceReleaser(docker=[_download_driver, _download_model], power=3).speedup()

    logger.success(
        ToolBox.runtime_report(
            motive="GET",
            action_name="ScaffoldInstaller",
            message="系统依赖下载完毕",
        )
    )


@logger.catch()
def test():
    """检查挑战者驱动版本是否适配"""
    ctx = get_challenge_ctx(silence=True)
    try:
        ctx.get("https://www.baidu.com")
    finally:
        ctx.quit()

    logger.success(
        ToolBox.runtime_report(
            motive="TEST",
            action_name="ScaffoldInstaller",
            message="驱动适配成功",
        )
    )
