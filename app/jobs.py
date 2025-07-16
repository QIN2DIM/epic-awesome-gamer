# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:57
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :
"""
from typing import List

from playwright.async_api import Page

from services.epic_agent_service import EpicAgent
from services.epic_authorization_service import EpicAuthorization

from settings import EpicSettings


async def add_games_to_cart(page: Page, urls: List[str] | None = None):
    """
    检测点功能，在登录后，控制前往指定站点点击 Add To Cart 操作
    Args:
        page:
        urls:

    Returns:

    """
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)

    urls = urls or [
        "https://store.epicgames.com/en-US/p/bloompunk-2fd3fd",
        "https://store.epicgames.com/en-US/p/fall-guys",
        "https://store.epicgames.com/en-US/p/lords-of-the-fallen-2-lords-of-the-fallen-free-coop-mode-81b41f",
        "https://store.epicgames.com/en-US/p/once-upon-a-puppet-08ad66",
    ]
    await agent.epic_games.add_promotion_to_cart(page, urls=urls)
    await page.goto("https://store.epicgames.com/en-US/cart", wait_until="networkidle")
    await page.wait_for_timeout(5000)


async def collect_games(page: Page):
    """
    采集周免游戏
    Args:
        page:

    Returns:

    """
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)
    await agent.collect_epic_games()


async def authorize(page: Page):
    epic_settings = EpicSettings()
    agent = EpicAuthorization(page, epic_settings)
    await agent.invoke()
