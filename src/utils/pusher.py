# -*- coding: utf-8 -*-
# Time       : 2022/9/25 13:01
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
import typing
from collections import deque
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import apprise


@dataclass
class MessageBody:
    url: str
    title: str
    result: str
    dlc: bool = None


@dataclass
class MessageQueue:
    _elements: typing.Deque[MessageBody] = None

    def __post_init__(self):
        self._elements = self._elements or deque()

    def get(self) -> typing.Optional[MessageBody]:
        return self._elements.popleft() if self._elements else None

    def put(self, element: typing.Union[MessageBody, dict]):
        if isinstance(element, MessageBody):
            self._elements.append(element)
        elif isinstance(element, dict):
            self._elements.append(MessageBody(**element))

    def __len__(self):
        return 0 if not self._elements else len(self._elements)

    def empty(self):
        return self.__len__() == 0


class MessagePusher:
    _dividing_width = 26
    _dividing_char = "="

    _copyright = "https://github.com/QIN2DIM/epic-awesome-gamer"
    _copyright_markdown = [
        "Author: [「QIN2DIM」](https://github.com/QIN2DIM)",
        f"GitHub: [「Epic免费人」]({_copyright})",
    ]
    _copyright_text = ["Author: QIN2DIM", "GitHub: QIN2DIM/epic-awesome-gamer"]

    def __init__(
        self,
        servers,
        player: str,
        inline_docker: typing.List[MessageBody],
        key_images: typing.List[str] = None,
    ):
        """

        :param servers:
        :param player:
        :param inline_docker:
        :type servers: List[str]
        """
        self.title = "EpicAwesomeGamer 运行报告"
        self.servers = servers
        self.player = player
        # 消息去重
        self.inline_docker: typing.List[MessageBody] = list(
            {r.url: r for r in inline_docker}.values()
        )
        # 游戏概念插画链接（CDN链接）
        self.key_images = key_images

        self.surprise = apprise.Apprise()

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
        # 去除指纹链接前台化
        u = urlparse(server)
        is_preview_ = "yes" if "preview=no" not in u.query.lower() else "no"
        server = f"{u.scheme}://{u.netloc}{u.path}?format=markdown&&preview={is_preview_}"
        inline_docker = copy(self.inline_docker)

        # 创建预览插画
        _preview = []
        if inline_docker:
            _preview = [f"[​]({random.choice(inline_docker).url or self._copyright})"]
        # 使用 CDN 插画绕开 Talon 的请求监控
        if self.key_images:
            cdn_image_url = random.choice(self.key_images)
            if (
                isinstance(cdn_image_url, str)
                and cdn_image_url.startswith("https://")
                and "cdn" in cdn_image_url
            ):
                _preview = [f"[​]({cdn_image_url})"]
        # 创建粗体标题
        _title = [f"*{self.title}*"]
        # 编排正文消息
        context_textbox, _ = self.for_general(inline_docker, _copyright=self._copyright_markdown)
        # 拼接消息
        context_textbox = _preview + _title + context_textbox
        return context_textbox, "", server

    def for_general(
        self, inline_docker: typing.List[MessageBody], _copyright: typing.List[str] = None
    ):
        _inline_textbox = self._copyright_text if _copyright is None else _copyright
        _inline_textbox += ["<周免游戏>".center(self._dividing_width, self._dividing_char)]
        if not inline_docker:
            _inline_textbox += [f"[{date_format_now()}] 🛴 暂无待认领的周免游戏"]
        else:
            _game_textbox = []
            _dlc_textbox = []
            for element in inline_docker:
                if not element.dlc:
                    _game_textbox.append(f"[{element.result}] {element.title}")
                else:
                    _dlc_textbox.append(f"[{element.result}] {element.title}")
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


def date_format_now() -> str:
    return str(datetime.now()).split(".", maxsplit=1)[0]
