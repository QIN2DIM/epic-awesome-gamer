# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import logging
import os
import random
import shutil
import sys
import warnings
from datetime import datetime
from datetime import timedelta
from typing import List, Union, Dict, Optional, Any
from urllib.parse import urlparse
from urllib.request import getproxies

import apprise
import cloudscraper
import pytz
import requests
import undetected_chromedriver as uc
import yaml
from bs4 import BeautifulSoup
from gevent.queue import Queue
from loguru import logger
from lxml import etree  # skipcq: BAN-B410 - Ignore credible sources
from selenium.webdriver import Chrome, ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import get_browser_version_from_os, ChromeType

StandardContext = type(Chrome)
ChallengerContext = type(uc.Chrome)

warnings.filterwarnings("ignore", category=FutureWarning)


class MessagePusher:
    _dividing_width = 28
    _dividing_char = "="

    _copyright = "https://github.com/QIN2DIM/epic-awesome-gamer"
    _copyright_markdown = [
        "Author: [「QIN2DIM」](https://github.com/QIN2DIM)",
        f"GitHub: [「Epic免费人」]({_copyright})",
    ]
    _copyright_text = ["Author: QIN2DIM", "GitHub: QIN2DIM/epic-awesome-gamer"]

    def __init__(self, servers, player: str, inline_docker: list, key_images: List[str] = None):
        """

        :param servers:
        :param player:
        :param inline_docker:
        :type servers: List[str]
        """
        self.servers = servers
        self.player = player
        _inline_docker = {r["url"]: r for r in inline_docker}

        self.title = "EpicAwesomeGamer 运行报告"

        self.inline_docker = list(_inline_docker.values())
        self.surprise = apprise.Apprise()

        # 游戏概念插画链接（CDN链接）
        self.key_images = key_images

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 注册 Apprise 消息推送框架
        for server in self.servers:
            if server.startswith("tgram://"):
                inline_textbox, title, server = self.for_telegram(server)
            else:
                inline_textbox, title = self.for_general(self.inline_docker)
            self.surprise.add(server)
            self.surprise.notify(body="\n".join(inline_textbox), title=title)
            self.surprise.clear()

    def for_telegram(self, server: str):
        u = urlparse(server)

        # 去除指纹链接前台化
        is_preview_ = "yes" if "preview=no" not in u.query.lower() else "no"

        server = f"{u.scheme}://{u.netloc}{u.path}?format=markdown&&preview={is_preview_}"

        inline_docker = self.inline_docker.copy()

        # illustrations
        _preview = [f"[​]({random.choice(inline_docker).get('url', self._copyright)})"]
        if self.key_images:
            cdn_image_url = random.choice(self.key_images)
            if (
                isinstance(cdn_image_url, str)
                and cdn_image_url.startswith("https://")
                and "cdn" in cdn_image_url
            ):
                _preview = [f"[​]({cdn_image_url})"]

        _title = [f"*{self.title}*"]

        for game_obj in inline_docker:
            game_obj["name"] = game_obj["name"].replace("《", "").replace("》", "")

        context_textbox, _ = self.for_general(inline_docker, _copyright=self._copyright_markdown)

        context_textbox = _preview + _title + context_textbox
        return context_textbox, "", server

    def for_general(self, inline_docker, _copyright: List[str] = None):
        _inline_textbox = self._copyright_text if _copyright is None else _copyright
        _inline_textbox += ["<周免游戏>".center(self._dividing_width, self._dividing_char)]
        if not inline_docker:
            _inline_textbox += [f"[{ToolBox.date_format_now()}] 🛴 暂无待认领的周免游戏"]
        else:
            _game_textbox = []
            _dlc_textbox = []
            for game_obj in inline_docker:
                if not game_obj.get("dlc"):
                    _game_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
                else:
                    _dlc_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
            _inline_textbox.extend(_game_textbox)
            if _dlc_textbox:
                _inline_textbox += ["<附加内容>".center(self._dividing_width, self._dividing_char)]
                _inline_textbox.extend(_dlc_textbox)
        _inline_textbox += [
            "<操作统计>".center(self._dividing_width, self._dividing_char),
            f"Player: {self.player}",
            f"Total: {inline_docker.__len__()}",
        ]

        return _inline_textbox, self.title


class ToolBox:
    """可移植的工具箱"""

    logger_tracer = Queue()
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
    def date_format_now(
        mode: Optional[str] = None, zone: Optional[str] = None, threshold: Optional[int] = None
    ) -> str:
        """
        输出格式化日期
        :param threshold:
        :param zone: 时区
        :param mode: with [file log threshold]
            - file：符合文件标准　yyyy-mm-dd
            - log：人类可读 yyyy-mm-dd HH:MM:SS
        :return:
        """
        mode = "log" if mode is None else mode
        zone = "Asia/Shanghai" if zone is None else zone
        threshold = 30 if threshold is None else threshold
        timezone = pytz.timezone(zone)

        format_date: str = ""
        if mode == "file":
            format_date = str(datetime.now(timezone)).split(" ", maxsplit=1)[0]
        elif mode == "log":
            format_date = str(datetime.now(timezone)).split(".", maxsplit=1)[0]
        elif mode == "threshold":
            format_date = str(datetime.now(timezone) + timedelta(seconds=threshold))
        return format_date

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


def _patch_headless(ctx: Chrome, silence: bool = True):
    if not silence:
        return
    logger.debug("patch headless")
    ctx.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator.connection, 'rtt', {
                        get: () => 200
                })"""
        },
    )
    ctx.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(Notification, 'permission', {
                    get: () => "default"
                })
            """
        },
    )

    ctx.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator.plugins, 'length', {
                    get: () => 5
                })
            """
        },
    )


def get_ctx(silence: Optional[bool] = None) -> StandardContext:
    """普通的 Selenium 驱动上下文，用于常规并发任务"""
    options = ChromeOptions()

    silence = True if silence is None or "linux" in sys.platform else silence
    if silence is True:
        options.add_argument("--log-level=3")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")

    # 使用 ChromeDriverManager 托管服务，自动适配浏览器驱动
    return Chrome(ChromeDriverManager(log_level=0).install(), options=options)


def get_challenge_ctx(
    silence: Optional[bool] = None, user_data_dir: Optional[str] = None
) -> ChallengerContext:
    """挑战者驱动 用于处理人机挑战"""
    silence = True if silence is None or "linux" in sys.platform else silence

    # - Use chromedriver cache to improve application startup speed
    # - Requirement: undetected-chromedriver >= 3.1.5.post2
    logging.getLogger("WDM").setLevel(logging.NOTSET)
    driver_executable_path = ChromeDriverManager(log_level=0).install()
    version_main = get_browser_version_from_os(ChromeType.GOOGLE).split(".")[0]

    # Modify necessary browser parameters
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")

    # Unified Challenge Language
    os.environ["LANGUAGE"] = "zh"
    options.add_argument(f"--lang={os.getenv('LANGUAGE', '')}")

    # Create challenger
    logger.debug(ToolBox.runtime_report("__Context__", "ACTIVATE", "🎮 激活挑战者上下文"))

    ctx = uc.Chrome(
        headless=silence,
        options=options,
        driver_executable_path=driver_executable_path,
        user_data_dir=user_data_dir,
    )

    # Record necessary startup information
    hook_ = "GitHub Action" if os.getenv("GITHUB_ACTIONS") else "base"
    logger.debug(f"Setup info: hook={hook_} platform={sys.platform}")

    _patch_headless(ctx, silence)
    return ctx
