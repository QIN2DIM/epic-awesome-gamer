# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:24
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from .agent import EpicGames, Game, CompletedOrder, get_promotions, get_order_history

from .player import EpicPlayer

__all__ = [
    "EpicGames",
    "Game",
    "CompletedOrder",
    "get_order_history",
    "get_promotions",
    "EpicPlayer",
]
