# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:43
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :
"""
import asyncio

from jobs import collect_week_free_games, add_week_free_games_to_cart


async def run_1():
    await collect_week_free_games.invoke()


async def main():
    await add_week_free_games_to_cart.invoke()


if __name__ == '__main__':
    asyncio.run(main())
