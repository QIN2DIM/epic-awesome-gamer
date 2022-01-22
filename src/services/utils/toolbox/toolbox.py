# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
import random
import shutil
import socket
import sys
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse

import colorama
import pytz
import yaml
from cloudscraper import create_scraper
from loguru import logger
from selenium.webdriver import ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

colorama.init(autoreset=True)


class ToolBox:
    @staticmethod
    def echo(msg: str, level: int):
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
    def date_format_life_cycle(life_cycle: int, tz="Asia/Shanghai") -> str:
        """

        :param life_cycle: 生命周期（小时）
        :param tz: 时区
        :return:
        """
        timezone = pytz.timezone(tz)
        date_life_cycle = datetime.now(timezone) + timedelta(hours=life_cycle)
        return str(date_life_cycle).split(".")[0]

    @staticmethod
    def is_stale_date(end_date: str) -> bool:
        """
        判断过期

        :param end_date: 结束时间
        :return:
        """
        end_date = datetime.fromisoformat(end_date)
        now_date = datetime.fromisoformat(ToolBox.date_format_now())

        return end_date < now_date

    @staticmethod
    def runtime_report(action_name: str, motive="RUN", message: str = "", **params) -> str:
        flag_ = ">> {} [{}]".format(motive, action_name)
        if message != "":
            flag_ += " {}".format(message)
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])
        return flag_

    @staticmethod
    def reset_url(url: str, path: str = "", get_domain: bool = False) -> str:
        """

        :param get_domain:
        :param url: 需要还原的链接
        :param path: 需要添加的地址路径 `/` 开头
        :return:
        """
        url_obj = urlparse(url)
        pure_url = f"{url_obj.scheme}://{url_obj.netloc}{path}"

        return pure_url if get_domain is False else url_obj.netloc

    @staticmethod
    def transfer_cookies(api_cookies: str or List[dict]) -> str or list:
        """
        将 cookies 转换为可携带的 Request Header
        :param api_cookies: api.get_cookies() or cookie_body
        :return:
        """
        if type(api_cookies) == str:
            return [{"name": i.split("=")[0], "value": i.split("=")[1]} for i in api_cookies.split("; ")]
        return "; ".join([f"{i['name']}={i['value']}" for i in api_cookies])

    @staticmethod
    def handle_html(url):
        headers = {
            "accept-language": "zh-CN",
        }

        scraper = create_scraper()
        response = scraper.get(url, timeout=10, allow_redirects=False, headers=headers)

        return response, response.status_code

    @staticmethod
    def check_local_network(test_server: tuple = None):

        test_server = ("www.baidu.com", 443) if test_server is None else test_server

        s = socket.socket()
        s.settimeout(3)

        try:
            status_code = s.connect_ex(test_server)
            return True if status_code == 0 else False
        # 可能原因：本地断网
        except socket.gaierror:
            return False
        # 超时或积极拒绝
        except (TimeoutError, ConnectionRefusedError):
            return False
        # port must be 0-65535.
        except OverflowError:
            return ToolBox.check_local_network(test_server=None)
        finally:
            s.close()

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


def _set_ctx(ua: bool = None):
    """

    :param ua: 挑战者不需要指定UA，会留下指纹特征。
    :return:
    """
    options = ChromeOptions()
    if ua:
        options.add_argument('--user-agent="{}"'.format(ToolBox.fake_user_agent()))
    options.add_argument("--log-level=3")
    options.add_argument("--lang=zh-CN")  # 可能仅在 Windows 生效
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--no-sandbox")
    return options


def get_ctx(silence: bool = None):
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver import Chrome

    silence = True if silence is None else silence

    options = _set_ctx(ua=True)
    if silence is True:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")

    # 使用 ChromeDriverManager 托管服务，自动适配浏览器驱动
    service = Service(ChromeDriverManager(log_level=0).install())
    return Chrome(options=options, service=service)  # noqa


def get_challenge_ctx(silence: bool = None):
    from undetected_chromedriver import Chrome

    silence = True if silence is None else silence

    # 针对部署环境的优化调节
    if "linux" in sys.platform:
        silence = True

    logger.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "激活挑战者上下文"))
    return Chrome(options=_set_ctx(), headless=silence)
