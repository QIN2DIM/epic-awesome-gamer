# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:24
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
from .epic_games import EpicGames, EpicSettings
from .helper.get_orders import get_promotions, get_order_history

__all__ = ['get_promotions', 'get_order_history', 'EpicGames', 'EpicSettings']
