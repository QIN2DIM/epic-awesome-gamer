# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import logging
import os
import shutil
import sys
import warnings
from collections import deque
from dataclasses import dataclass
from typing import List, Union, Dict, Optional, Any
from urllib.request import getproxies

import cloudscraper
import requests
import yaml
from bs4 import BeautifulSoup
from loguru import logger
from lxml import etree  # skipcq: BAN-B410 - Ignore credible sources
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.getLogger("WDM").setLevel(logging.NOTSET)

warnings.filterwarnings("ignore", category=FutureWarning)


class ToolBox:
    """可移植的工具箱"""

    logger_tracer = deque()
    motion = None

    @staticmethod
    def check_sample_yaml(path_output: str, path_sample: str) -> Optional[Dict[str, Any]]:
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
            print(
                "Please do not delete the system built-in `config-sample.yaml` "
                "Make sure it is located in the project root directory"
            )

    @staticmethod
    def runtime_report(action_name: str, motive: str = "RUN", message: str = "", **params) -> str:
        """格式化输出"""
        flag_ = f">> {motive} [{action_name}]"
        if message != "":
            flag_ += f" {message}"
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])

        # feat(pending): 将系统级日志按序插入消息队列
        # ToolBox.logger_tracer.put(flag_)

        return flag_

    @staticmethod
    def transfer_cookies(
        api_cookies: Union[List[Dict[str, str]], str]
    ) -> Union[str, List[Dict[str, str]]]:
        """
        将 cookies 转换为可携带的 Request Header
        :param api_cookies: api.get_cookies() or cookie_body
        :return:
        """
        if isinstance(api_cookies, str):
            return [
                {"name": i.split("=")[0], "value": i.split("=")[1]} for i in api_cookies.split("; ")
            ]
        return "; ".join([f"{i['name']}={i['value']}" for i in api_cookies])

    @staticmethod
    def secret_email(email: str, domain: Optional[bool] = None) -> str:
        """去除敏感数据"""
        domain = True if domain is None else domain
        prefix, suffix = email.split("@")
        secrets_prefix = f"{prefix[0]}***{prefix[-1]}"
        return f"{secrets_prefix}@{suffix}" if domain else secrets_prefix

    @staticmethod
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
            sink=sys.stdout,
            colorize=True,
            level="DEBUG",
            format=event_logger_format,
            diagnose=False,
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

    @staticmethod
    def handle_html(url_, cookie: str = None, allow_redirects=False):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.4896.75 Safari/537.36 Edg/100.0.1185.36"
        }
        if cookie is not None and isinstance(cookie, str):
            headers.update({"cookie": cookie})
        scraper = cloudscraper.create_scraper()
        response_ = scraper.get(url_, headers=headers, allow_redirects=allow_redirects)
        tree_ = etree.HTML(response_.content)
        return tree_, response_

    @staticmethod
    def gen_motion():
        def pull_motion():
            url = "https://github.com/QIN2DIM/hcaptcha-challenger/wiki/Motion"
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.27"
            }
            res = requests.get(url, headers=headers, proxies=getproxies())
            soup = BeautifulSoup(res.text, "html.parser")
            body = soup.find("div", id="wiki-body").find("p")
            return [i.split(",") for i in body.text.split("\n")][:200]

        ToolBox.motion = ToolBox.motion or pull_motion()
        return ToolBox.motion or pull_motion()


@dataclass
class DriverWrapper:
    options = ChromeOptions()
    path: str = ""

    def __post_init__(self):
        self.options.add_argument("--log-level=3")
        self.options.add_argument("--disable-software-rasterizer")
        self.options.add_argument("--disable-gpu")

        # Unified Challenge Language
        os.environ["LANGUAGE"] = "zh"
        self.options.add_argument(f"--lang={os.getenv('LANGUAGE', '')}")

        # - Use chromedriver cache to improve application startup speed
        # - Requirement: undetected-chromedriver >= 3.1.5.post4
        self.path = self.path or ChromeDriverManager().install()


def get_ctx(silence: Optional[bool] = None):
    """普通的 Selenium 驱动上下文，用于常规并发任务"""
    driver_wrapper = DriverWrapper()
    options = driver_wrapper.options

    silence = True if silence is None or "linux" in sys.platform else silence
    if silence is True:
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")

    # 使用 ChromeDriverManager 托管服务，自动适配浏览器驱动
    return Chrome(service=Service(driver_wrapper.path), options=options)
