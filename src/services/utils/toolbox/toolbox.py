# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import shutil
import sys
from datetime import datetime
from typing import List, Union, Dict, Optional

import colorama
import yaml
from loguru import logger
from selenium.webdriver import ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

colorama.init(autoreset=True if "win" in sys.platform else False)


class ToolBox:
    @staticmethod
    def echo(msg: str, level: int) -> str:
        """
        控制台彩色输出
        :param msg:
        :param level: 1:[✓] 0:[×] 2:[...] 3:[*]
        :return:
        """
        print(f"[{str(datetime.now()).split('.')[0]}]", end=" ")
        if level == 1:
            print(colorama.Fore.GREEN + "[✓]", end=" ")
        elif level == 0:
            print(colorama.Fore.RED + "[×]", end=" ")
        # 阻塞任务
        elif level == 2:
            print(colorama.Fore.BLUE + "[...]", end=" ")
        # debug
        elif level == 3:
            print(colorama.Fore.CYAN + "[*]", end=" ")
        elif level == 1013:
            print(colorama.Fore.CYAN + "💥", end=" ")
        print(msg)
        return ">"

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
                ToolBox.echo("系统配置模板文件(config-sample.yaml)缺失。", 0)
                raise FileNotFoundError

            # 项目未初始化，自动拷贝模板文件
            if not os.path.exists(path_output):
                ToolBox.echo("系统配置文件(config.yaml)缺失", 0)
                shutil.copy(path_sample, path_output)
                ToolBox.echo("生成配置文件，请合理配置并重启项目-->config.yaml", 1)
                sys.exit()

            # 配置正常，读取配置参数
            with open(path_output, "r", encoding="utf8") as stream:
                config_ = yaml.safe_load(stream.read())
                if __name__ == "__main__":
                    ToolBox.echo("读取配置文件-->config.yaml", 1)
                    print(config_)

            return config_

        # 需要到项目仓库重新拉取文件
        except FileNotFoundError:
            ToolBox.echo("Please do not delete the `system built-in config-sample.yaml` "
                         "Make sure it is located in the project root directory", 3)

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
    options.add_argument("--no-sandbox")
    return options


def get_ctx(silence: Optional[bool] = None):
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver import Chrome

    silence = True if silence is None else silence

    options = _set_ctx()
    if silence is True:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")

    # 使用 ChromeDriverManager 托管服务，自动适配浏览器驱动
    service = Service(ChromeDriverManager(log_level=0).install())
    return Chrome(options=options, service=service)  # noqa


def get_challenge_ctx(silence: Optional[bool] = None):
    from undetected_chromedriver import Chrome

    silence = True if silence is None else silence

    # 针对部署环境的优化调节
    if "linux" in sys.platform:
        silence = True

    logger.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "激活挑战者上下文"))
    return Chrome(options=_set_ctx(), headless=silence)
