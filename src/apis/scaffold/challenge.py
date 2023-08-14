# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from loguru import logger

from services.bricklayer.game import GameClaimer
from services.models import Ranni


def check_token():
    """刷新上下文身份令牌"""
    logger.info("STARTUP [ScaffoldChallenge] 正在更新身份令牌")
    claimer = GameClaimer()
    ranni = Ranni.from_mode(mode="epic-games")
    ranni.boost(tasks=claimer.cookie_manager.refresh_ctx_cookies)
    logger.success(f"GET [ChallengeRunner] 任务结束 - path={claimer.cookie_manager.path_ctx_cookies}")
