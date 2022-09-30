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
    logger.info(
        ToolBox.runtime_report(
            motive="STARTUP", action_name="ScaffoldChallenge", message="正在更新身份令牌..."
        )
    )

    # [🌀] 激活人机挑战
    if not bricklayer.cookie_manager.refresh_ctx_cookies(silence=silence):
        return

    # [🌀] 读取新的身份令牌
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    # [🌀] 保存身份令牌
    with open(PATH_USR_COOKIES, "w", encoding="utf8") as file:
        file.write(ToolBox.transfer_cookies(ctx_cookies))

    logger.success(
        ToolBox.runtime_report(
            motive="GET", action_name="ChallengeRunner", message="玩家饼干已到货。", path=PATH_USR_COOKIES
        )
    )
