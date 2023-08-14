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
from typing import List, Dict, Callable, Any

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


def transfer_cookies(api_cookies: List[Dict[str, str]] | str) -> str | List[Dict[str, str]]:
    """
    ctx_cookies --> request_cookies
    request_cookies --> ctx_cookies

    :param api_cookies: api.get_cookies() or cookie_body
    :return:
    """
    if isinstance(api_cookies, str):
        return [
            {"name": i.split("=")[0], "value": i.split("=")[1]} for i in api_cookies.split("; ")
        ]
    return "; ".join([f"{i['name']}={i['value']}" for i in api_cookies])


def from_dict_to_model(cls, data: Dict[str, Any]):
    return cls(
        **{
            key: (data[key] if val.default == val.empty else data.get(key, val.default))
            for key, val in inspect.signature(cls).parameters.items()
        }
    )


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
            evasion_code = Path(f"puppeteer-extra-plugin-stealth/evasions/{e}/index.js").read_text(
                encoding="utf8"
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

    def boost(self, *, tasks: Callable[[SyncContext], None] | List, **kwargs):
        logger.info("startup FireEngine")

        with sync_playwright() as p:
            context = p.firefox.launch_persistent_context(
                user_data_dir=self._user_data_dir,
                headless=False,
                locale="zh-CN",
                record_video_dir=self._record_dir,
                record_har_path=self._record_har_path,
                args=["--hide-crash-restore-bubble"],
                **kwargs
            )
            self._apply_stealth(context)
            self._patch_cookies(context)

            if not isinstance(tasks, list):
                tasks = [tasks]
            for container in tasks:
                logger.info("launch container")
                container(context)
            if self.state_path:
                context.storage_state(path=self.state_path)
            context.close()
