# -*- coding: utf-8 -*-
# Time       : 2023/8/14 17:04
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import sys
import time
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Literal

from loguru import logger

from services.settings import config
from utils.toolbox import Tarnished


@dataclass
class Cookie(ABC):
    cookie_path: Path

    @property
    def is_available(self) -> bool:
        return True

    def load(self):
        pass

    def flush(self):
        pass


@dataclass
class EpicCookie(Cookie):
    pass


@dataclass
class Player:
    epic_email: str
    epic_password: str
    """
    Epic Account
    """

    mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"] = "epic-games"
    """
    Context relay mode
    """

    user_data_dir: Path = Path(__file__).parent.parent.joinpath("user_data_dir")
    """
    Mount user cache
    - database
    - user_data_dir
        - alice@games # runtime user_data_dir
            - context
            - record
                - captcha.mp4
                - eg-record.har
            - ctx_cookie.json
            - ctx_store.json
            - order_history.json
        - alice@unreal
            - context
            - record
                - captcha.mp4
                - eg-record.har
            - ctx_cookie.json
        - alice@gog
        - alice@steam
    """

    username: str = "Lucy"
    """
    Epic username
    """

    repository: Dict[str, Any] = field(default_factory=dict)
    """
    Player's game repository
    """

    ctx_cookie: Cookie = None
    """
    Persistent Playwright state
    """

    def __post_init__(self):
        self.repository = self.repository or {}
        if not self.ctx_cookie:
            if self.mode == "epic-games":
                pass

    @classmethod
    def from_mode(cls, mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"]):
        epic_email, epic_password = config.epic_email, config.epic_password
        if not all([epic_email, epic_password]):
            logger.critical("Email / Password information is incomplete")
            sys.exit(1)

        instance = cls(epic_email=epic_email, epic_password=epic_password, mode=mode)
        namespace = f"{epic_email.split('@')[0]}@{mode}"
        instance.user_data_dir = instance.user_data_dir.joinpath(namespace)

        for ck in ["browser_context", "record"]:
            ckp = instance.user_data_dir.joinpath(ck)
            ckp.mkdir(777, parents=True, exist_ok=True)

        return instance

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

    @property
    def ctx_store_path(self) -> Path:
        return self.user_data_dir.joinpath("ctx_store.json")

    @property
    def order_history_path(self) -> Path:
        return self.user_data_dir.joinpath("order_history.json")


class Ranni(Tarnished):
    """Web browser driver over Playwright"""

    def __init__(self, player: Player, **kwargs):
        super().__init__(**kwargs)
        self.player = player

    @classmethod
    def from_player(cls, player: Player):
        return cls(
            player=player,
            user_data_dir=player.browser_context_dir,
            record_dir=player.record_dir,
            record_har_path=player.record_har_path,
            state_path=player.ctx_cookie_path
        )

    @classmethod
    def from_mode(cls, mode: Literal["epic-games", "unreal", "gog", "apg", "xbox"]):
        player = Player.from_mode(mode)
        return cls(
            player=player,
            user_data_dir=player.browser_context_dir,
            record_dir=player.record_dir,
            record_har_path=player.record_har_path,
            state_path=player.ctx_cookie_path
        )
