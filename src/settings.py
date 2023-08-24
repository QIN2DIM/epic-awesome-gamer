# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from utils import init_log


@dataclass
class Project:
    src_dir = Path(__file__).parent
    root_dir = src_dir.parent
    config_path = src_dir.joinpath("config.json")

    logs_dir = root_dir.joinpath("logs")

    user_data_dir = root_dir.joinpath("user_data_dir")


@dataclass
class Config:
    epic_email: str
    epic_password: str
    """
    Epic Account
    """

    apprise_servers: List[str] = field(default_factory=list)
    """
    System Notification by apprise
    docs: https://github.com/caronc/apprise
    """

    cdn: str = ""
    """
    Set CDN to download AI models from GITHub release
    """

    @classmethod
    def from_json(cls, config_path: Path):
        try:
            _config: dict = json.loads(config_path.read_text())
        except FileNotFoundError:
            template = {"epic_email": "", "epic_password": "", "apprise_servers": []}
            data = json.dumps(template, indent=4, allow_nan=True, ensure_ascii=True)
            config_path.write_text(data)
            logger.info("初始化项目成功，请填写配置后重启项目")
            sys.exit(1)

        try:
            epic_email = os.environ.get("EPIC_EMAIL", _config.get("epic_email", ""))
            epic_password = os.environ.get("EPIC_PASSWORD", _config.get("epic_password", ""))
            apprise_servers = [os.environ[k] for k in os.environ if k.startswith("APPRISE_")]
            apprise_servers.extend(_config.get("apprise_servers", []))
            cdn = (
                "https://dl.capoo.xyz"
                if not os.getenv("GITHUB_REPOSITORY") and _config.get("enable_https_cdn")
                else ""
            )
        except KeyError:
            sys.exit(1)

        return cls(
            epic_email=epic_email,
            epic_password=epic_password,
            apprise_servers=apprise_servers,
            cdn=cdn,
        )


project = Project()
logger = init_log(
    error=project.logs_dir.joinpath("error.log"),
    runtime=project.logs_dir.joinpath("runtime.log"),
    serialize=project.logs_dir.joinpath("serialize.log"),
)
config = Config.from_json(project.config_path)
