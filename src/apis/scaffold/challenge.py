# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:

import typing

from loguru import logger
from playwright.sync_api import BrowserContext as SyncContext
from playwright.sync_api import sync_playwright
from undetected_playwright import stealth_sync

from services.bricklayer.game import GameClaimer
from services.settings import config


def fire(
        containers: typing.Union[typing.Callable[[SyncContext], None], typing.List],
        path_state: str,
        user_data_dir: str,
):
    with sync_playwright() as p:
        context = p.webkit.launch_persistent_context(
            user_data_dir=user_data_dir, headless=False, locale="zh-CN"
        )
        stealth_sync(context)
        if not isinstance(containers, list):
            containers = [containers]
        for container in containers:
            container(context)
        context.storage_state(path=path_state)
        context.close()


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
