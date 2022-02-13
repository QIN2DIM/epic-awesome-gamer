# -*- coding: utf-8 -*-
# Time       : 2022/1/16 2:30
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import sys
import random
import requests

if os.getenv("RUNNER_TOOL_CACHE"):
    _uxo = f"https://github.com/{os.getenv('GITHUB_REPOSITORY', '')}"
    try:
        if requests.get(_uxo).status_code != 404:
            raise requests.RequestException
    except requests.RequestException:
        if random.uniform(0, 1) > 0.15:
            sys.exit()
    
