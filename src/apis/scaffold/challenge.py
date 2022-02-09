# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.bricklayer import Bricklayer
from services.settings import PATH_USR_COOKIES, logger
from services.utils import ToolBox

bricklayer = Bricklayer()


def run():
    """刷新上下文身份令牌"""

    # [🌀] 激活人机挑战
    logger.info(
        ToolBox.runtime_report(
            motive="STARTUP", action_name="ScaffoldChallenge", message="正在更新身份令牌..."
        )
    )
    if not bricklayer.cookie_manager.refresh_ctx_cookies():
        return

    # [🌀] 读取新的身份令牌
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    # [🌀] 保存用户令牌
    with open(PATH_USR_COOKIES, "w", encoding="utf8") as file:
        file.write(ToolBox.transfer_cookies(ctx_cookies))

    logger.success(
        ToolBox.runtime_report(
            motive="GET",
            action_name="ChallengeRunner",
            message="玩家饼干已到货。",
            path=PATH_USR_COOKIES,
        )
    )
