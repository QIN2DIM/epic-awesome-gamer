# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import random
import shutil
import sys
from datetime import datetime
from typing import List, Union, Dict, Optional

import pytz
import yaml
from loguru import logger
from selenium.webdriver import ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager


class ToolBox:

    @staticmethod
    def check_sample_yaml(path_output: str, path_sample: str) -> dict:
        """
        检查模板文件是否存在，检查配置文件是否存在，读取系统配置返回

        :param path_output: 配置生成路径（user）
        :param path_sample: 模板文件路径（built-in）
        :return:
        """
        try:
            # 丢失模板文件
            if not os.path.exists(path_sample):
                print("[EXIT] 系统配置模板文件(config-sample.yaml)缺失。")
                raise FileNotFoundError

            # 项目未初始化，自动拷贝模板文件
            if not os.path.exists(path_output):
                print("系统配置文件(config.yaml)缺失")
                shutil.copy(path_sample, path_output)
                print("[EXIT] 生成配置文件，请合理配置并重启项目-->config.yaml")
                sys.exit()

            # 配置正常，读取配置参数
            with open(path_output, "r", encoding="utf8") as stream:
                config_ = yaml.safe_load(stream.read())
                if __name__ == "__main__":
                    print("读取配置文件-->config.yaml")
                    print(config_)

            return config_

        # 需要到项目仓库重新拉取文件
        except FileNotFoundError:
            print("Please do not delete the system built-in `config-sample.yaml` "
                  "Make sure it is located in the project root directory")

    @staticmethod
    def runtime_report(action_name: str, motive: str = "RUN", message: str = "", **params) -> str:
        flag_ = ">> {} [{}]".format(motive, action_name)
        if message != "":
            flag_ += " {}".format(message)
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])
        return flag_

    @staticmethod
    def transfer_cookies(api_cookies: Union[List[Dict[str, str]], str]) -> Union[str, List[Dict[str, str]]]:
        """
        将 cookies 转换为可携带的 Request Header
        :param api_cookies: api.get_cookies() or cookie_body
        :return:
        """
        if type(api_cookies) == str:
            return [{"name": i.split("=")[0], "value": i.split("=")[1]} for i in api_cookies.split("; ")]
        return "; ".join([f"{i['name']}={i['value']}" for i in api_cookies])

    @staticmethod
    def fake_user_agent() -> str:
        """Tip:指定UA可能会留下特征"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/97.0.4692.71 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62"
        ]
        return random.choice(user_agents)

    @staticmethod
    def date_format_now(mode="log", tz="Asia/Shanghai") -> str:
        """
        输出格式化日期
        :param tz: 时区
        :param mode: with [file log]
            - file：符合文件标准　yyyy-mm-dd
            - log：人类可读 yyyy-mm-dd HH:MM:SS
        :return:
        """
        timezone = pytz.timezone(tz)
        if mode == "file":
            return str(datetime.now(timezone)).split(" ")[0]
        if mode == "log":
            return str(datetime.now(timezone)).split(".")[0]

    @staticmethod
    def secret_email(email: str, domain: Optional[bool] = None) -> str:
        domain = True if domain is None else domain
        prefix, suffix = email.split("@")
        secrets_prefix = f"{prefix[0]}***{prefix[-1]}"
        return f"{secrets_prefix}@{suffix}" if domain else secrets_prefix


class InitLog:

    @staticmethod
    def init_log(**sink_path):
        event_logger_format = (
            "<g>{time:YYYY-MM-DD HH:mm:ss}</g> | "
            "<lvl>{level}</lvl> - "
            # "<c><u>{name}</u></c> | "
            "{message}"
        )
        logger.remove()
        logger.add(
            sink=sys.stdout,
            colorize=True,
            level="DEBUG",
            format=event_logger_format,
            diagnose=False
        )
        if sink_path.get("error"):
            logger.add(
                sink=sink_path.get("error"),
                level="ERROR",
                rotation="1 week",
                encoding="utf8",
                diagnose=False
            )
        if sink_path.get("runtime"):
            logger.add(
                sink=sink_path.get("runtime"),
                level="DEBUG",
                rotation="20 MB",
                retention="20 days",
                encoding="utf8",
                diagnose=False
            )
        return logger


def _set_ctx() -> ChromeOptions:
    options = ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_argument("--lang=zh-CN")  # 可能仅在 Windows 生效
    options.add_argument('--disable-dev-shm-usage')
    # options.add_argument("--no-sandbox")
    return options


def get_ctx(silence: Optional[bool] = None):
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver import Chrome

    silence = True if silence is None or "linux" in sys.platform else silence

    options = _set_ctx()
    if silence is True:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
    options.add_argument('--user-agent="{}"'.format(ToolBox.fake_user_agent()))
    # 使用 ChromeDriverManager 托管服务，自动适配浏览器驱动
    service = Service(ChromeDriverManager(log_level=0).install())
    return Chrome(options=options, service=service)  # noqa


def get_challenge_ctx(silence: Optional[bool] = None):
    from undetected_chromedriver import Chrome

    silence = True if silence is None or "linux" in sys.platform else silence

    logger.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "🎮 激活挑战者上下文"))
    return Chrome(options=_set_ctx(), headless=silence, version_main=97)
