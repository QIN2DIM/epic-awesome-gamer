# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import logging
import os
import sys
import typing
import warnings
from dataclasses import dataclass
from typing import List, Union, Dict

from loguru import logger
from selenium.webdriver import ChromeOptions
from undetected_chromedriver import Chrome as Challenger
from webdriver_manager.chrome import ChromeDriverManager

logging.getLogger("WDM").setLevel(logging.NOTSET)

warnings.filterwarnings("ignore", category=FutureWarning)


class ToolBox:
    """可移植的工具箱"""

    @staticmethod
    def runtime_report(action_name: str, motive: str = "RUN", message: str = "", **params) -> str:
        """格式化输出"""
        flag_ = f">> {motive} [{action_name}]"
        if message != "":
            flag_ += f" {message}"
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])
        return flag_

    @staticmethod
    def transfer_cookies(
        api_cookies: Union[List[Dict[str, str]], str]
    ) -> Union[str, List[Dict[str, str]]]:
        """
        ctx_cookies --> request_cookies
        request_cookies --> ctx_cookies

        :param api_cookies: api.get_cookies() or cookie_body
        :return:
        """
        if isinstance(api_cookies, str):
            return [
                {"name": i.split("=")[0], "value": i.split("=")[1]} for i in api_cookies.split("; ")
            ]
        return "; ".join([f"{i['name']}={i['value']}" for i in api_cookies])


def init_log(**sink_path):
    """初始化 loguru 日志信息"""
    event_logger_format = (
        "<g>{time:YYYY-MM-DD HH:mm:ss}</g> | "
        "<lvl>{level}</lvl> - "
        # "<c><u>{name}</u></c> | "
        "{message}"
    )
    logger.remove()
    logger.add(
        sink=sys.stdout, colorize=True, level="DEBUG", format=event_logger_format, diagnose=False
    )
    if sink_path.get("error"):
        logger.add(
            sink=sink_path.get("error"),
            level="ERROR",
            rotation="1 week",
            encoding="utf8",
            diagnose=False,
        )
    if sink_path.get("runtime"):
        logger.add(
            sink=sink_path.get("runtime"),
            level="DEBUG",
            rotation="20 MB",
            retention="20 days",
            encoding="utf8",
            diagnose=False,
        )
    return logger


@dataclass
class DriverWrapper:
    silence: bool = False
    path: str = ""
    options = ChromeOptions()

    def __post_init__(self):
        self.options.headless = self.silence

        self.options.add_argument("--log-level=3")
        self.options.add_argument("--disable-software-rasterizer")

        # Unified Challenge Language
        os.environ["LANGUAGE"] = "zh"
        self.options.add_argument(f"--lang={os.getenv('LANGUAGE', '')}")

        # Hook to headful xvfb server
        if "linux" in sys.platform or self.silence:
            self.options.add_argument("--disable-setuid-sandbox")
            self.options.add_argument("--disable-gpu")
            self.options.add_argument("--no-sandbox")
            self.options.add_argument("--no-xshm")
            self.options.add_argument("--disable-dev-shm-usage")
            self.options.add_argument("--no-first-run")

        if self.silence:
            self.options.add_argument("--window-size=1920,1080")
            self.options.add_argument("--start-maximized")

        # - Use chromedriver cache to improve application startup speed
        # - Requirement: undetected-chromedriver >= 3.1.5.post4
        self.path = self.path or ChromeDriverManager().install()


def get_challenge_ctx(silence: typing.Optional[bool] = None) -> Challenger:
    """挑战者驱动 用于处理人机挑战"""
    driver_wrapper = DriverWrapper(silence=silence)
    options = driver_wrapper.options
    if "linux" in sys.platform:
        logger.info("Please use `xvfb` to empower the headful Chrome.")
        logger.info("CMD: xvfb-run python3 main.py claim")
        if silence:
            raise RuntimeError("Please use `xvfb` to empower the headful Chrome.")
    logging.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "🎮 激活挑战者上下文"))
    return Challenger(options=options, driver_executable_path=driver_wrapper.path)
