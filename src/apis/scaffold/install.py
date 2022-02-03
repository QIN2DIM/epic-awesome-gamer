# -*- coding: utf-8 -*-
# Time       : 2022/1/20 16:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import sys

from webdriver_manager.chrome import ChromeDriverManager

from services.settings import DIR_MODEL, logger
from services.utils import YOLO, CoroutineSpeedup, ToolBox

_HOOK_CDN_PREFIX = "https://curly-shape-d178.qinse.workers.dev/"


def _sync_ctx():
    """
    下载最新版 google-chrome
    :return:
    """
    # Ubuntu
    if "linux" not in sys.platform:
        return

    logger.debug("同步 google-chrome 驱动版本...")
    os.system("apt-get update && apt-get install -y gcc wget")
    os.system("wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb >/dev/null")
    os.system("apt install ./google-chrome-stable_current_amd64.deb -y >/dev/null")
    os.system("rm -rf ./google-chrome-stable_current_amd64.deb")
    os.system("clear")


def _download_model(*args, **kwargs):
    """
    下载 YOLOv4 目标检测模型
    :param cdn:
    :return:
    """
    if not args:
        pass
    cdn = kwargs.get("cdn", False)

    _yolo = YOLO(dir_model=DIR_MODEL)
    if cdn is True and not _HOOK_CDN_PREFIX:
        _yolo.cfg["src"] = _HOOK_CDN_PREFIX + _yolo.cfg["src"]
        _yolo.weights["src"] = _HOOK_CDN_PREFIX + _yolo.weights["src"]

    logger.debug("下载 YOLOv4 目标检测模型...")
    _yolo.download_model()


def _download_driver(*args, **kwargs):
    """
    下载浏览器驱动。

    :return:
    """
    if not args:
        pass
    version = kwargs.get("version", "latest")

    logger.debug("适配 ChromeDriver...")
    ChromeDriverManager(version=version).install()


class PerformanceReleaser(CoroutineSpeedup):
    def __init__(self, docker, power=None):
        super(PerformanceReleaser, self).__init__(docker=docker, power=power)

    def control_driver(self, task, *args, **kwargs):
        try:
            task(*args, **kwargs)
        except Exception as e:  # noqa
            logger.exception(e)


def run(cdn: bool = False):
    """
    下载项目运行所需的各项依赖。

    :return:
    """
    logger.debug(ToolBox.runtime_report(
        motive="BUILD",
        action_name="RequirementInstaller",
        message="正在下载系统依赖",
        params=f"cdn={cdn}"
    ))
    docker = [
        _download_driver,
        _download_model
    ]

    # _sync_ctx()
    booster = PerformanceReleaser(docker=docker, power=3)
    booster.go(cdn=cdn)

    logger.success(ToolBox.runtime_report(
        motive="GET",
        action_name="RequirementInstaller",
        message="系统依赖下载完毕",
        params=f"cdn={cdn}"
    ))
