# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
from os.path import (
    join,
    dirname,
    exists
)

# ---------------------------------------------------
# TODO [√]工程根目录定位
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
# TODO [√]服务器日志配置
# ---------------------------------------------------
from services.utils import InitLog

logger = InitLog.init_log(
    error=join(DIR_LOG, "error.log"),
    runtime=join(DIR_LOG, "runtime.log")
)

# ---------------------------------------------------
# 路径补全
# ---------------------------------------------------
for _pending in [
    PROJECT_DATABASE,
    DIR_MODEL,
    DIR_EXPLORER,
    DIR_COOKIES,
    DIR_TEMP_CACHE, DIR_CHALLENGE,
    DIR_LOG,
]:
    if not exists(_pending):
        os.mkdir(_pending)

# ---------------------------------------------------
# 合并配置文件参数
# ---------------------------------------------------
from config import *

__all__ = [
    # ------------------------------
    # SETTINGS
    # ------------------------------
    "logger", "DIR_CHALLENGE",
    "DIR_COOKIES",
    "DIR_TEMP_CACHE", "DIR_EXPLORER", "PATH_USR_COOKIES",
    "DIR_MODEL",

    # ------------------------------
    # CONFIG
    # ------------------------------
    "USER_PASSWORD", "USER_EMAIL", "SCHEDULER_SETTINGS",
    "MESSAGE_PUSHER_SETTINGS",
]
