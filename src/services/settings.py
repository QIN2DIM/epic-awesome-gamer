# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import sys
from datetime import datetime
from os.path import join, dirname
from typing import Dict, Any, Optional

from services.utils import ToolBox

__all__ = [
    # ------------------------------
    # SETTINGS
    # ------------------------------
    "logger",
    "DIR_CHALLENGE",
    "DIR_COOKIES",
    "DIR_TEMP_CACHE",
    "DIR_EXPLORER",
    "PATH_USR_COOKIES",
    "DIR_MODEL",
    "PATH_RAINBOW",
    # ------------------------------
    # CONFIG
    # ------------------------------
    "EPIC_PASSWORD",
    "EPIC_EMAIL",
    "MESSAGE_PUSHER_SETTINGS",
    "PLAYER",
]
__version__ = "0.3.3.dev"

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
# YOLO模型
DIR_MODEL = join(PROJECT_ROOT, "model")
# Reinforcement of memory
PATH_RAINBOW = join(DIR_MODEL, "rainbow.yaml")
# Cookie 工作目录
DIR_COOKIES = join(PROJECT_DATABASE, "cookies")
PATH_USR_COOKIES = join(DIR_COOKIES, "user_cookies.txt")
# FreeGame Mining Workspace
DIR_EXPLORER = join(PROJECT_DATABASE, "explorer")
# 运行缓存目录
DIR_TEMP_CACHE = join(PROJECT_DATABASE, "temp_cache")
# 挑战缓存
DIR_CHALLENGE = join(DIR_TEMP_CACHE, "_challenge")
# 服务日志目录
DIR_LOG = join(PROJECT_DATABASE, "logs")
# ---------------------------------------------------
# [√]服务器日志配置
# ---------------------------------------------------
logger = ToolBox.init_log(
    error=join(DIR_LOG, "error.log"), runtime=join(DIR_LOG, "runtime.log")
)

# ---------------------------------------------------
# 路径补全
# ---------------------------------------------------
for _pending in [
    PROJECT_DATABASE,
    DIR_MODEL,
    DIR_EXPLORER,
    DIR_COOKIES,
    DIR_TEMP_CACHE,
    DIR_CHALLENGE,
    DIR_LOG,
]:
    if not os.path.exists(_pending):
        os.mkdir(_pending)
"""
================================================== ʕ•ﻌ•ʔ ==================================================
                                  若您并非项目开发者 请勿修改以下变量的默认参数
================================================== ʕ•ﻌ•ʔ ==================================================

                                            Enjoy it -> ♂ main.py
"""
config_ = ToolBox.check_sample_yaml(
    path_output=join(dirname(dirname(__file__)), "config.yaml"),
    path_sample=join(dirname(dirname(__file__)), "config-sample.yaml"),
)
# --------------------------------
# [√] 账号信息
# --------------------------------
# 不建议在公有库上创建工作流运行项目，有仓库禁用风险
EPIC_EMAIL: Optional[str] = config_.get("EPΙC_EMAΙL", "")
EPIC_PASSWORD: Optional[str] = config_.get("EPΙC_PASSWΟRD", "")

# --------------------------------
# [※] 消息推送配置
# --------------------------------
MESSAGE_PUSHER_SETTINGS: Optional[Dict[str, Any]] = config_.get(
    "message_pusher_settings", {}
)
# Apprise Server 泛映射
PUSHER: Optional[Dict[str, Optional[str]]] = MESSAGE_PUSHER_SETTINGS.get("pusher", {})
# 匿名设置
PLAYER: Optional[str] = MESSAGE_PUSHER_SETTINGS.get("player", "")
# --------------------------------
# [※] 补全语法模板
# --------------------------------
if not EPIC_EMAIL:
    EPIC_EMAIL = os.getenv("EPΙC_EMAΙL", "")
if not EPIC_PASSWORD:
    EPIC_PASSWORD = os.getenv("EPΙC_PASSWΟRD", "")

try:
    for server in PUSHER:
        if not PUSHER[server]:
            PUSHER[server] = os.getenv(server, "")
except KeyError as e:
    print(f"[进程退出] 核心配置文件被篡改 error={e}")
    sys.exit()

_CONVERTER = ["沫雯喂", "辰丽", "荪彦孜", "有坷唯", "郑姊祺", "弹蓶蓶", "王飛"]
PLAYER = os.getenv("PLAYER", "") if not PLAYER else PLAYER
if PLAYER in ["", None]:
    PLAYER = f"{random.choice(_CONVERTER)}({datetime.now().day})"
# --------------------------------
# [√] 阻止缺省配置
# --------------------------------
if not all((EPIC_EMAIL, EPIC_PASSWORD)):
    print("[进程退出] 账号信息未配置或相关变量不合法")
    sys.exit()

if not any(PUSHER.values()):
    MESSAGE_PUSHER_SETTINGS["enable"] = False
