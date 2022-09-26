# -*- coding: utf-8 -*-
# Time       : 2022/9/25 13:01
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
import typing
from datetime import datetime, timedelta
from urllib.parse import urlparse

import apprise
import pytz


class MessagePusher:
    _dividing_width = 28
    _dividing_char = "="

    _copyright = "https://github.com/QIN2DIM/epic-awesome-gamer"
    _copyright_markdown = [
        "Author: [「QIN2DIM」](https://github.com/QIN2DIM)",
        f"GitHub: [「Epic免费人」]({_copyright})",
    ]
    _copyright_text = ["Author: QIN2DIM", "GitHub: QIN2DIM/epic-awesome-gamer"]

    def __init__(
        self, servers, player: str, inline_docker: list, key_images: typing.List[str] = None
    ):
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

    def for_general(self, inline_docker, _copyright: typing.List[str] = None):
        _inline_textbox = self._copyright_text if _copyright is None else _copyright
        _inline_textbox += ["<周免游戏>".center(self._dividing_width, self._dividing_char)]
        if not inline_docker:
            _inline_textbox += [f"[{date_format_now()}] 🛴 暂无待认领的周免游戏"]
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


def date_format_now(
    mode: typing.Optional[str] = None,
    zone: typing.Optional[str] = None,
    threshold: typing.Optional[int] = None,
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
