# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import shutil
import sys
import time
import typing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from services.utils.toolbox import init_log


@dataclass
class Project:
    root = Path(__file__).parent.parent
    database = root.joinpath("database")

    claim_history_dir = database.joinpath("claim_history")
    logs_dir = root.joinpath("logs")

    user_data_dir = root.joinpath("user_data_dir")
    record_dir = database.joinpath("record")

    def __post_init__(self):
        for ck in [self.logs_dir, self.user_data_dir, self.record_dir, self.claim_history_dir]:
            ck.mkdir(777, parents=True, exist_ok=True)

    @property
    def record_har_path(self) -> Path:
        return self.record_dir.joinpath(f"eg-{int(time.time())}.har")


project = Project()

logger = init_log(
    error=project.logs_dir.joinpath("error.log"),
    runtime=project.logs_dir.joinpath("runtime.log"),
    serialize=project.logs_dir.joinpath("serialize.log"),
)


@dataclass
class Config:
    epic_email: str = ""
    epic_password: str = ""
    message_pusher: MessagePusher = None
    config_yaml: typing.Dict[str, Any] = field(default_factory=dict)

    HTTPS_CDN = ""

    def __post_init__(self):
        self.config_yaml = self.config_yaml or {}
        self.message_pusher = self.message_pusher or MessagePusher(
            **self.config_yaml.get("message_pusher_settings", {})
        )
        # [GitHub Workflow && Container] Motion Global Values
        for data_template in [self.config_yaml, os.environ]:
            for kcy in data_template:
                if not data_template[kcy]:
                    continue
                if kcy in ["EPIC_EMAIL", "EPΙC_EMAΙL"] and not self.epic_email:
                    self.epic_email = data_template[kcy]
                elif kcy in ["EPIC_PASSWORD", "EPΙC_PASSWΟRD"] and not self.epic_password:
                    self.epic_password = data_template[kcy]
                elif kcy.startswith("PUSHER_") and not self.message_pusher.pusher.get(kcy):
                    self.message_pusher.enable = True
                    self.message_pusher.pusher[kcy] = data_template[kcy]
                elif kcy == "PLAYER" and not self.message_pusher.player:
                    self.message_pusher.player = data_template[kcy]
                elif kcy == "GITHUB_REVERSE_PROXY":
                    self.set_reverse_proxy(data_template[kcy])

    def set_reverse_proxy(self, https_cdn: str):
        if os.getenv("GITHUB_REPOSITORY"):
            return
        if https_cdn == "default":
            self.HTTPS_CDN = "https://dl.capoo.xyz"
        elif u := urlparse(https_cdn):
            if u.scheme.startswith("https") and u.netloc:
                self.HTTPS_CDN = https_cdn

    def diagnose(self):
        if not self.epic_email:
            raise RuntimeError("[PROCESS EXIT] EPIC_EMAIL NOT CONFIGURED OR ILLEGAL")
        if not self.epic_email:
            raise RuntimeError("[PROCESS EXIT] EPIC_PASSWORD NOT CONFIGURED OR ILLEGAL")
        self.message_pusher.diagnose()


def check_sample_yaml(path_output: str, path_sample: str):
    """
    检查模板文件是否存在，检查配置文件是否存在，读取系统配置返回

    :param path_output: 配置生成路径（user）
    :param path_sample: 模板文件路径（built-in）
    :return:
    """
    config_yaml = {}

    if not os.path.exists(path_sample):
        return config_yaml
    if not os.path.exists(path_output):
        logger.warning("系统配置文件(config.yaml)缺失")
        logger.info("[EXIT] 生成配置文件，请合理配置并重启项目-->config.yaml")
        shutil.copy(path_sample, path_output)
        sys.exit()
    with open(path_output, "r", encoding="utf8") as stream:
        config_yaml = yaml.safe_load(stream.read())
    return config_yaml


config = Config(
    config_yaml=check_sample_yaml(
        path_output=join(PROJECT_SRC, "config.yaml"),
        path_sample=join(PROJECT_SRC, "config-sample.yaml"),
    )
)
config.diagnose()
