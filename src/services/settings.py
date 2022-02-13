# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import sys
from os.path import join, dirname
from typing import Dict, Union, Any

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
    # ------------------------------
    # CONFIG
    # ------------------------------
    "EPIC_PASSWORD",
    "EPIC_EMAIL",
    "SCHEDULER_SETTINGS",
    "MESSAGE_PUSHER_SETTINGS",
]
__version__ = "0.1.7.dev"

"""
================================================ ʕ•ﻌ•ʔ ================================================
                            (·▽·)欢迎嫖友入座，请跟随提示合理配置项目启动参数
================================================ ʕ•ﻌ•ʔ ================================================
[√]核心配置 [※]边缘参数
"""
config_ = ToolBox.check_sample_yaml(
    path_output=join(dirname(dirname(__file__)), "config.yaml"),
    path_sample=join(dirname(dirname(__file__)), "config-sample.yaml"),
)
# --------------------------------
# [√] 账号信息
# --------------------------------
# 不建议在公有库上创建工作流运行项目，有仓库禁用风险
EPIC_EMAIL: str = config_.get("EPΙC_EMAΙL", "")
EPIC_PASSWORD: str = config_.get("EPΙC_PASSWΟRD", "")

# --------------------------------
# [※] 本地化语言设置
# --------------------------------
LOCALE_LANG: str = config_.get("LOCALE_LANG", "")

# --------------------------------
# [※] 定任务配置
# --------------------------------
SCHEDULER_SETTINGS: Dict[str, Union[int, bool]] = config_.get("scheduler", {})

# --------------------------------
# [※] 消息推送配置
# --------------------------------
MESSAGE_PUSHER_SETTINGS: Dict[str, Any] = config_.get("message_pusher_settings", {})
PUSHER = MESSAGE_PUSHER_SETTINGS.get("pusher", {})
"""
================================================== ʕ•ﻌ•ʔ ==================================================
                                  若您并非项目开发者 请勿修改以下变量的默认参数
================================================== ʕ•ﻌ•ʔ ==================================================

                                            Enjoy it -> ♂ main.py
"""
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
# --------------------------------
# [√] 阻止缺省配置
# --------------------------------
if not all((EPIC_EMAIL, EPIC_PASSWORD)):
    sys.exit()

if not any(PUSHER.values()):
    MESSAGE_PUSHER_SETTINGS["enable"] = False

# ---------------------------------------------------
# [√]工程根目录定位
# ---------------------------------------------------
# 系统根目录
PROJECT_ROOT = dirname(dirname(__file__))
# 文件数据库目录
PROJECT_DATABASE = join(PROJECT_ROOT, "database")
# YOLO模型
DIR_MODEL = join(PROJECT_ROOT, "model")
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
