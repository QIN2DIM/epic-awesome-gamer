# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Callable, Any

from loguru import logger
from playwright.sync_api import BrowserContext as SyncContext
from playwright.sync_api import sync_playwright


def init_log(**sink_channel):
    event_logger_format = "<g>{time:YYYY-MM-DD HH:mm:ss}</g> | <lvl>{level}</lvl> - {message}"
    serialize_format = event_logger_format + "- {extra}"
    logger.remove()
    logger.add(
        sink=sys.stdout, colorize=True, level="DEBUG", format=serialize_format, diagnose=False
    )
    if sink_channel.get("error"):
        logger.add(
            sink=sink_channel.get("error"),
            level="ERROR",
            rotation="1 week",
            encoding="utf8",
            diagnose=False,
            format=serialize_format,
        )
    if sink_channel.get("runtime"):
        logger.add(
            sink=sink_channel.get("runtime"),
            level="DEBUG",
            rotation="20 MB",
            retention="20 days",
            encoding="utf8",
            diagnose=False,
            format=serialize_format,
        )
    if sink_channel.get("serialize"):
        logger.add(
            sink=sink_channel.get("serialize"),
            level="DEBUG",
            format=serialize_format,
            encoding="utf8",
            diagnose=False,
            serialize=True,
        )
    return logger


def from_dict_to_model(cls, data: Dict[str, Any]):
    return cls(
        **{
            key: (data[key] if val.default == val.empty else data.get(key, val.default))
            for key, val in inspect.signature(cls).parameters.items()
        }
    )


AgentMan = Callable[[SyncContext], None]
AgentSu = Callable[[SyncContext, ...], None]


class Tarnished:
    def __init__(
        self,
        user_data_dir: Path,
        *,
        record_dir: Path | None = None,
        record_har_path: Path | None = None,
        state_path: Path | None = None,
    ):
        self._user_data_dir = user_data_dir
        self._record_dir = record_dir
        self._record_har_path = record_har_path
        self.state_path = state_path

    @staticmethod
    def _apply_stealth(context: SyncContext):
        enabled_evasions = [
            "chrome.app",
            "chrome.csi",
            "chrome.loadTimes",
            "chrome.runtime",
            "iframe.contentWindow",
            "media.codecs",
            "navigator.hardwareConcurrency",
            "navigator.languages",
            "navigator.permissions",
            "navigator.plugins",
            "navigator.webdriver",
            "sourceurl",
            "webgl.vendor",
            "window.outerdimensions",
        ]

        for e in enabled_evasions:
            evasion_code = (
                Path(__file__)
                .parent.joinpath(f"puppeteer-extra-plugin-stealth/evasions/{e}/index.js")
                .read_text(encoding="utf8")
            )
            context.add_init_script(evasion_code)

        return context

    @staticmethod
    def _patch_cookies(context: SyncContext):
        five_days_ago = datetime.now() - timedelta(days=5)
        cookie = {
            "name": "OptanonAlertBoxClosed",
            "value": five_days_ago.isoformat(),
            "domain": ".epicgames.com",
            "path": "/",
        }
        context.add_cookies([cookie])

    def storage_state(self, context: SyncContext):
        if self.state_path:
            logger.info("Storage ctx_cookie", path=self.state_path)
            context.storage_state(path=self.state_path)

    def execute(self, *, sequence: AgentMan | AgentSu, parameters: Dict[str, Any] = None, **kwargs):
        with sync_playwright() as p:
            context = p.firefox.launch_persistent_context(
                user_data_dir=self._user_data_dir,
                headless=False,
                locale="zh-CN",
                record_video_dir=self._record_dir,
                record_har_path=self._record_har_path,
                args=["--hide-crash-restore-bubble"],
                **kwargs,
            )
            self._apply_stealth(context)
            self._patch_cookies(context)

            if not isinstance(sequence, list):
                sequence = [sequence]
            for container in sequence:
                logger.info("Execute task", name=container.__name__)
                kws = {}
                params = inspect.signature(container).parameters
                if parameters and isinstance(parameters, dict):
                    for name in params:
                        if name != "context" and name in parameters:
                            kws[name] = parameters[name]
                if not kws:
                    container(context)
                else:
                    container(context, **kws)
            context.close()
