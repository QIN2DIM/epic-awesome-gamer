# -*- coding: utf-8 -*-
# Time       : 2022/7/4 23:03
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os.path
from typing import Optional

from services.settings import DIR_LOG


def get_logger(src: Optional[str] = "runtime"):
    path_runtime_log = os.path.join(DIR_LOG, "runtime.log")
    path_error_log = os.path.join(DIR_LOG, "error.log")
    dir_screenshot = os.path.join(os.path.dirname(DIR_LOG), "challenge_result")
