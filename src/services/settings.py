# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import shutil
import sys
import typing
from dataclasses import dataclass, field
from datetime import datetime
from os.path import join, dirname
from typing import Any

import yaml

from services.utils import ToolBox

__all__ = [
    # ------------------------------
    # SETTINGS
    # ------------------------------
    "logger",
    "DIR_COOKIES",
    "DIR_USERS",
    "DIR_EXPLORER",
    "PATH_USR_COOKIES",
    "DIR_SCREENSHOT",
    "DIR_LOG",
    # ------------------------------
    # CONFIG
    # ------------------------------
    "SynergyTunnel",
    "config",
]

"""
================================================ ʕ•ﻌ•ʔ ================================================
                                            (·▽·)欢迎嫖友入座
================================================ ʕ•ﻌ•ʔ ================================================
[√]核心配置 [※]边缘参数
"""
# ---------------------------------------------------
# [√]工程根目录定位
# ---------------------------------------------------
# 系统根目录
PROJECT_ROOT = dirname(dirname(__file__))
# 文件数据库目录
PROJECT_DATABASE = join(PROJECT_ROOT, "database")
# Cookie 工作目录
DIR_COOKIES = join(PROJECT_DATABASE, "cookies")
PATH_USR_COOKIES = join(DIR_COOKIES, "user_cookies.txt")
DIR_USERS = join(PROJECT_DATABASE, "users")
# FreeGame Mining Workspace
DIR_EXPLORER = join(PROJECT_DATABASE, "explorer")
# 服务日志目录
DIR_LOG = join(PROJECT_DATABASE, "logs")
DIR_SCREENSHOT = join(DIR_LOG, "screenshot")
# ---------------------------------------------------
# [√]服务器日志配置
# ---------------------------------------------------
logger = ToolBox.init_log(error=join(DIR_LOG, "error.log"), runtime=join(DIR_LOG, "runtime.log"))

# ---------------------------------------------------
# 路径补全
# ---------------------------------------------------
for _pending in [PROJECT_DATABASE, DIR_EXPLORER, DIR_COOKIES, DIR_USERS, DIR_LOG, DIR_SCREENSHOT]:
    os.makedirs(_pending, exist_ok=True)
"""
================================================== ʕ•ﻌ•ʔ ==================================================
                                  若您并非项目开发者 请勿修改以下变量的默认参数
================================================== ʕ•ﻌ•ʔ ==================================================

                                            Enjoy it -> ♂ main.py
"""


@dataclass
class MessagePusher:
    pusher: typing.Dict[str, str] = field(default_factory=dict)
    player: str = ""
    enable: bool = False

    ACTIVE_PUSHERS: typing.List[str] = field(default_factory=list)
    ACTIVE_SERVERS: typing.List[str] = field(default_factory=list)

    # fmt:off
    CONVERTER = [
        "沫雯喂", "辰丽", "荪彦孜", "有坷唯", "郑姊祺", "弹蓶蓶", "王飛",
        "Makise Kurisu", "Rem", "Lacus Clyne", "Megumin", "Misaka Mikoto",
        "Yukino", "ゆずりは いのり", "Gokou Ruri", "がえん とおえ", "Yuuki Asuna",
    ]

    # fmt:on

    def __post_init__(self):
        self.pusher["PUSHER_QIN2DIM"] = ""

    def diagnose(self):
        if not any(self.pusher.values()):
            self.enable = False
        self.ACTIVE_PUSHERS = [_p[0] for _p in self.pusher.items() if _p[-1]]
        self.ACTIVE_SERVERS = [_p[-1] for _p in self.pusher.items() if _p[-1]]
        self.player = self.player or f"{random.choice(self.CONVERTER)}({datetime.now().day})"


@dataclass
class Config:
    epic_email: str = ""
    epic_password: str = ""
    message_pusher: MessagePusher = None
    config_yaml: typing.Dict[str, Any] = field(default_factory=dict)

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
                elif kcy.startswith("PUSHER_"):
                    self.message_pusher.pusher[kcy] = data_template[kcy]
                elif kcy == "PLAYER":
                    self.message_pusher.player = data_template[kcy]
                elif kcy == "ENABLE_PUSHER":
                    self.message_pusher.enable = True

    def diagnose(self):
        assert self.epic_email, "[PROCESS EXIT] EPIC_EMAIL NOT CONFIGURED OR ILLEGAL"
        assert self.epic_password, "[PROCESS EXIT] EPIC_PASSWORD NOT CONFIGURED OR ILLEGAL"
        self.message_pusher.diagnose()
        return self

    def to_dict(self):
        mirror = self.__dict__
        mirror["message_pusher_settings"] = self.message_pusher.__dict__
        return mirror


def check_sample_yaml(path_output: str, path_sample: str) -> typing.Optional[typing.Dict[str, Any]]:
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
        path_output=join(PROJECT_ROOT, "config.yaml"),
        path_sample=join(PROJECT_ROOT, "config-sample.yaml"),
    )
)
config.diagnose()


class SynergyTunnel:
    ARMOR = None
    _CHANNEL = {}

    LEAVES = []

    # 暂存任务促销
    url2name = {}

    @staticmethod
    def set_combat(k, v):
        SynergyTunnel._CHANNEL.update({k: v})

    @staticmethod
    def get_combat(k):
        return SynergyTunnel._CHANNEL.get(k)

    @staticmethod
    def is_convert() -> bool:
        return bool(SynergyTunnel.LEAVES)
