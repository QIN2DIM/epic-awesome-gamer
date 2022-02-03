# -*- coding: utf-8 -*-
# Time       : 2022/1/30 1:49
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger
from services.utils import (
    ToolBox
)

SILENCE = True

bricklayer = Bricklayer(silence=SILENCE)
explorer = Explorer(silence=SILENCE)


def run():
    # 更新身份令牌
    if not bricklayer.cookie_manager.refresh_ctx_cookies(verify=True):
        return
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    # 扫描商城促销活动，返回“0折”商品的名称与商城链接
    limited_free_game_objs = explorer.get_the_limited_free_game(ctx_cookies)
    if not limited_free_game_objs.get("urls"):
        return
    urls = limited_free_game_objs["urls"]

    # 优先处理常规情况 urls.__len__() == 1
    for url in urls:
        logger.debug(ToolBox.runtime_report(
            motive="STARTUP",
            action_name="ScaffoldClaim",
            message="🍜 正在为玩家领取周免游戏",
            game=f"『{limited_free_game_objs[url]}』"
        ))
        bricklayer.get_free_game(
            page_link=url,
            ctx_cookies=ctx_cookies,
            challenge=True
        )
