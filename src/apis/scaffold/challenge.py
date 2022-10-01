# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import typing

from loguru import logger

from services.bricklayer.game import GameClaimer
from services.settings import PATH_USR_COOKIES, config
from services.utils.toolbox import ToolBox

bricklayer = GameClaimer(email=config.epic_email, password=config.epic_password)


def run(silence: typing.Optional[bool] = None):
    """刷新上下文身份令牌"""
    logger.info("STARTUP [ScaffoldChallenge] 正在更新身份令牌")
    if bricklayer.cookie_manager.refresh_ctx_cookies(silence=silence):
        ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()
        with open(PATH_USR_COOKIES, "w", encoding="utf8") as file:
            file.write(ToolBox.transfer_cookies(ctx_cookies))
    logger.success(f"GET [ChallengeRunner] 任务结束 - path={PATH_USR_COOKIES}")
