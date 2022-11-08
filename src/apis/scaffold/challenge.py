# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from loguru import logger

from services.bricklayer.game import GameClaimer
from services.settings import config
from services.utils.toolbox import fire


def check_token():
    """刷新上下文身份令牌"""
    logger.info("STARTUP [ScaffoldChallenge] 正在更新身份令牌")
    claimer = GameClaimer(email=config.epic_email, password=config.epic_password)
    fire(
        containers=claimer.cookie_manager.refresh_ctx_cookies,
        path_state=claimer.cookie_manager.path_ctx_cookies,
        user_data_dir=claimer.cookie_manager.user_data_dir,
    )
    logger.success(f"GET [ChallengeRunner] 任务结束 - path={claimer.cookie_manager.path_ctx_cookies}")
