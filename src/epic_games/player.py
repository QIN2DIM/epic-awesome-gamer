# -*- coding: utf-8 -*-
# Time       : 2023/8/14 17:04
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import abc
import json
import time
from abc import ABC
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict
from typing import Literal

import httpx

from settings import config, project


@dataclass
class EpicCookie:
    cookies: Dict[str, str] = field(default_factory=dict)
    """
    cookies in the Request Header
    """

    URL_VERIFY_COOKIES = "https://www.epicgames.com/account/personal"

    @classmethod
    def from_state(cls, fp: Path):
        """Jsonify cookie from Playwright"""
        cookies = {}
        try:
            data = json.loads(fp.read_text())["cookies"]
            cookies = {ck["name"]: ck["value"] for ck in data}
        except (FileNotFoundError, KeyError):
            pass
        return cls(cookies=cookies)

    def is_available(self) -> bool | None:
        if not self.cookies:
            return
        with suppress(httpx.ConnectError):
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203",
                "origin": "https://store.epicgames.com/zh-CN/p/orwell-keeping-an-eye-on-you",
            }
            resp = httpx.get(self.URL_VERIFY_COOKIES, headers=headers, cookies=self.cookies)
            return resp.status_code == 200

    def reload(self, fp: Path) -> Dict[str, str] | None:
        try:
            data = json.loads(fp.read_text())["cookies"]
            self.cookies = {ck["name"]: ck["value"] for ck in data}
            return self.cookies
        except (FileNotFoundError, KeyError):
            pass


@dataclass
class Player(ABC):
    email: str
    password: str
    """
    Player's account
    """

    mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"]
    """
    Game Platform
    """

    user_data_dir: Path = project.user_data_dir
    """
    Mount user cache
    - database
    - user_data_dir
        - games@email # runtime user_data_dir
            - context
            - record
                - captcha.mp4
                - eg-record.har
            - ctx_cookie.json
            - ctx_store.json
            - order_history.json
        - unreal@email
            - context
            - record
                - captcha.mp4
                - eg-record.har
        - gog@alice
        - xbox@alice
    """

    def __post_init__(self):
        namespace = f"{self.mode}@{self.email.split('@')[0]}"
        self.user_data_dir = self.user_data_dir.joinpath(namespace)
        for ck in ["browser_context", "record"]:
            ckp = self.user_data_dir.joinpath(ck)
            ckp.mkdir(parents=True, exist_ok=True)

    @classmethod
    @abc.abstractmethod
    def from_account(cls, *args, **kwargs):
        raise NotImplementedError

    @property
    def browser_context_dir(self) -> Path:
        return self.user_data_dir.joinpath("browser_context")

    @property
    def record_dir(self) -> Path:
        return self.user_data_dir.joinpath("record")

    @property
    def record_har_path(self) -> Path:
        return self.record_dir.joinpath(f"eg-{int(time.time())}.har")

    @property
    def ctx_cookie_path(self) -> Path:
        return self.user_data_dir.joinpath("ctx_cookie.json")


@dataclass
class EpicPlayer(Player):
    _ctx_cookies: EpicCookie = None

    def __post_init__(self):
        super().__post_init__()
        self._ctx_cookies = EpicCookie.from_state(fp=self.ctx_cookie_path)

    @classmethod
    def from_account(cls):
        return cls(email=config.epic_email, password=config.epic_password, mode="epic-games")

    @property
    def ctx_store_path(self) -> Path:
        return self.user_data_dir.joinpath("ctx_store.json")

    @property
    def order_history_path(self) -> Path:
        return self.user_data_dir.joinpath("order_history.json")

    @property
    def ctx_cookies(self) -> EpicCookie:
        return self._ctx_cookies

    @property
    def cookies(self) -> Dict[str, str]:
        return self._ctx_cookies.cookies

    @cookies.setter
    def cookies(self, cookies: Dict[str, str]):
        self._ctx_cookies.cookies = cookies
