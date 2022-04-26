# -*- coding: utf-8 -*-
# Time       : 2022/1/20 16:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import sys
import webbrowser

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import get_browser_version_from_os

from services.settings import DIR_MODEL, logger, PATH_RAINBOW
from services.utils import YOLO
from services.utils import get_challenge_ctx
from services.utils import sk_recognition


def _download_model(onnx_prefix: str = None):
    """下载 YOLOv4 目标检测模型"""
    logger.debug("Downloading YOLOv5(ONNX) object detection model...")

    YOLO(dir_model=DIR_MODEL, onnx_prefix=onnx_prefix).download_model()


def _download_driver():
    """下载浏览器驱动"""
    logger.debug("Downloading ChromeDriver...")

    # 自动下载并授权对应版本的 ChromeDriver
    browser_version = get_browser_version_from_os("google-chrome")
    if browser_version != "UNKNOWN":
        return ChromeDriverManager(version="latest").install()

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


def _download_rainbow():
    logger.debug("Downloading Reinforcement of Memory | Rainbow Table...")

    sk_recognition.SKRecognition.sync_rainbow(path_rainbow=PATH_RAINBOW, convert=True)


def run(onnx_prefix: str = None):
    """下载项目运行所需的各项依赖"""
    logger.debug("正在下载系统依赖")
    _download_driver()
    _download_model(onnx_prefix=onnx_prefix)
    _download_rainbow()
    logger.success("系统依赖下载完毕")


@logger.catch()
def test():
    """检查挑战者驱动版本是否适配"""
    ctx = get_challenge_ctx(silence=True)
    try:
        ctx.get("https://www.baidu.com")
    finally:
        ctx.quit()

    logger.success("驱动适配成功")
