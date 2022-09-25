# -*- coding: utf-8 -*-
# Time       : 2022/1/20 16:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import sys
import webbrowser
from typing import Optional

import hcaptcha_challenger as solver
from loguru import logger
from webdriver_manager.chrome import ChromeType
from webdriver_manager.core.utils import get_browser_version_from_os


def download_driver():
    # Detect environment variable `google-chrome`.
    browser_version = get_browser_version_from_os(ChromeType.GOOGLE)
    if browser_version != "UNKNOWN":
        return

    # `google-chrome` is missing from environment variables, prompting players to install manually.
    logger.critical(
        "The current environment variable is missing `google-chrome`, "
        "please install Chrome for your system"
    )
    logger.info(
        "Ubuntu: https://linuxize.com/post/how-to-install-google-chrome-web-browser-on-ubuntu-20-04/"
    )
    logger.info(
        "CentOS 7/8: https://linuxize.com/post/how-to-install-google-chrome-web-browser-on-centos-7/"
    )
    if "linux" not in sys.platform:
        webbrowser.open("https://www.google.com/chrome/")

    logger.info("Re-execute the `install` scaffolding command after the installation is complete.")


def do(yolo_onnx_prefix: Optional[str] = None, upgrade: Optional[bool] = False):
    """下载项目运行所需的各项依赖"""
    onnx_prefix = yolo_onnx_prefix or solver.Prefix.YOLOv6n
    solver.install(onnx_prefix=onnx_prefix, upgrade=upgrade)


@logger.catch()
def test():
    """Check if the Challenger driver version is compatible"""
