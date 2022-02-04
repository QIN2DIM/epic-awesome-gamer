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

"""
================================================ ʕ•ﻌ•ʔ ================================================
                            (·▽·)欢迎嫖友入座，请跟随提示合理配置项目启动参数
================================================ ʕ•ﻌ•ʔ ================================================
[√]核心配置 [※]边缘参数
"""
config_ = ToolBox.check_sample_yaml(path_output=join(dirname(__file__), "config.yaml"),
                                    path_sample=join(dirname(__file__), "config-sample.yaml"))

# --------------------------------
# [√] 账号信息
# --------------------------------
USER_EMAIL: str = config_.get("EMAIL", "")
USER_PASSWORD: str = config_.get("PASSWORD", "")

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
__version__ = "0.1.5.dev"

# --------------------------------
# [※] 补全语法模板
# --------------------------------
if not USER_EMAIL:
    USER_EMAIL = os.getenv("EPIC_EMAIL", "")
if not USER_PASSWORD:
    USER_PASSWORD = os.getenv("EPIC_PASSWORD", "")

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
if not all((USER_EMAIL, USER_PASSWORD)):
    sys.exit()

if not any(PUSHER.values()):
    MESSAGE_PUSHER_SETTINGS["enable"] = False
