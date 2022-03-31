# -*- coding: utf-8 -*-
# Time       : 2022/1/16 2:30
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import sys

import requests

if os.getenv("RUNNER_TOOL_CACHE"):
    _uxo = f"https://github.com/{os.getenv('GITHUB_REPOSITORY', '')}"
    try:
        if requests.get(_uxo).status_code != 404:
            raise requests.RequestException
    except requests.RequestException:
        print(
            "[Warning] 禁止在 fork 分支上运行工作流，请创建私有工作流。\n"
            "详见 https://blog.echosec.top/epic-awesome-gamer/zh/docs/player/hosting-deployment/privatisation/"
        )
        if random.uniform(0, 1) > 0.15:
            sys.exit()
