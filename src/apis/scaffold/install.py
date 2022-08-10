# -*- coding: utf-8 -*-
# Time       : 2022/1/20 16:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import hashlib
import os
import sys
import webbrowser
from typing import Optional

from webdriver_manager.chrome import ChromeType
from webdriver_manager.utils import get_browser_version_from_os

from services.settings import DIR_MODEL, logger, PATH_RAINBOW_YAML, PATH_OBJECTS_YAML
from services.utils import YOLO, SKRecognition, PluggableONNXModels
from services.utils import get_challenge_ctx


def download_driver():
    """下载浏览器驱动"""
    # 自动下载并授权对应版本的 ChromeDriver
    browser_version = get_browser_version_from_os(ChromeType.GOOGLE)
    if browser_version != "UNKNOWN":
        return

    # 环境变量中缺少 `google-chrome` 提示玩家手动安装
    logger.critical("当前环境变量缺少 `google-chrome`，请为你的设备手动安装 Chrome 浏览器。")
    logger.info(
        "Ubuntu: https://linuxize.com/post/how-to-install-google-chrome-web-browser-on-ubuntu-20-04/"
    )
    logger.info(
        "CentOS 7/8: https://linuxize.com/post/how-to-install-google-chrome-web-browser-on-centos-7/"
    )
    if "linux" not in sys.platform:
        webbrowser.open("https://www.google.com/chrome/")

    logger.info("安装完毕后重新执行 `install` 脚手架指令。")


def download_yolo_model(onnx_prefix):
    YOLO(dir_model=DIR_MODEL, onnx_prefix=onnx_prefix).download_model()


def refresh_pluggable_onnx_model(upgrade: Optional[bool] = None):
    def need_to_refresh():
        _flag = "15482b5ab24d600efdf2def260c830ab1ba2f04ce011ddfb885adc2d8e1797da"
        if not os.path.exists(PATH_RAINBOW_YAML):
            return True
        with open(PATH_RAINBOW_YAML, "rb") as file:
            return hashlib.sha256(file.read()).hexdigest() != _flag

    if need_to_refresh():
        SKRecognition.sync_rainbow(path_rainbow=PATH_RAINBOW_YAML, convert=True)
        PluggableONNXModels(PATH_OBJECTS_YAML).summon(dir_model=DIR_MODEL, upgrade=upgrade)


def run(model: str = None, upgrade: Optional[bool] = None):
    """下载项目运行所需的各项依赖"""
    download_driver()
    download_yolo_model(onnx_prefix=model)
    refresh_pluggable_onnx_model(upgrade=upgrade)


@logger.catch()
def test():
    """检查挑战者驱动版本是否适配"""
    ctx = get_challenge_ctx(silence=True)
    try:
        ctx.get("https://www.epicgames.com/account/personal")
    finally:
        ctx.quit()

    logger.success("驱动适配成功")
