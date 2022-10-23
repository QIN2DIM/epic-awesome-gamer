# -*- coding: utf-8 -*-
# Time       : 2022/10/22 23:35
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import json
import os
import typing
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext as ASyncContext
from playwright.sync_api import BrowserContext as SyncContext
from playwright.sync_api import sync_playwright


def _from_file(name):
    return Path(__file__).parent.joinpath(name).read_text()


@dataclass
class _Skills:
    chrome_app = _from_file("js/chrome.csi.js")
    chrome_csi = _from_file("js/chrome.app.js")
    chrome_hairline = _from_file("js/chrome.hairline.js")
    chrome_load_times = _from_file("js/chrome.load.times.js")
    chrome_runtime = _from_file("js/chrome.runtime.js")
    generate_magic_arrays = _from_file("js/generate.magic.arrays.js")
    iframe_content_window = _from_file("js/iframe.contentWindow.js")
    media_codecs = _from_file("js/media.codecs.js")
    navigator_hardware_concurrency = _from_file("js/navigator.hardwareConcurrency.js")
    navigator_languages = _from_file("js/navigator.languages.js")
    navigator_permissions = _from_file("js/navigator.permissions.js")
    navigator_platform = _from_file("js/navigator.platform.js")
    navigator_plugins = _from_file("js/navigator.plugins.js")
    navigator_user_agent = _from_file("js/navigator.userAgent.js")
    navigator_vendor = _from_file("js/navigator.vendor.js")
    sourceurl = _from_file("js/sourceurl.js")
    utils = _from_file("js/utils.js")
    webgl_vendor = _from_file("js/webgl.vendor.js")
    window_outerdimensions = _from_file("js/window.outerdimensions.js")
    webdriver = _from_file("js/webdriver.js")


@dataclass
class NinjaConfig:
    """Default feature at anti-EpicTalonService"""

    chrome_app: typing.Optional[bool] = True
    chrome_csi: typing.Optional[bool] = True
    chrome_hairline: typing.Optional[bool] = True
    chrome_load_times: typing.Optional[bool] = True
    chrome_runtime: typing.Optional[bool] = True
    iframe_content_window: typing.Optional[bool] = True  # It is counterproductive to selenium
    media_codecs: typing.Optional[bool] = True
    navigator_languages: typing.Optional[bool] = True
    navigator_permissions: typing.Optional[bool] = True
    navigator_platform: typing.Optional[bool] = False
    navigator_plugins: typing.Optional[bool] = True
    navigator_vendor: typing.Optional[bool] = False
    sourceurl: typing.Optional[bool] = True
    webgl_vendor: typing.Optional[bool] = True
    window_outerdimensions: typing.Optional[bool] = True
    patch_headless: typing.Optional[bool] = True

    vendor = "Intel Inc."
    renderer = "Intel Iris OpenGL Engine"
    nav_vendor = "Google Inc."
    nav_platform = None
    nav_user_agent = None
    languages: typing.Tuple[str] = ("en-US", "en")
    runOnInsecureOrigins: typing.Optional[bool] = None

    def __post_init__(self):
        self.skills = _Skills()

    @property
    def enabled_features(self):
        opts = json.dumps(
            {
                "webgl_vendor": self.vendor,
                "webgl_renderer": self.renderer,
                "navigator_vendor": self.nav_vendor,
                "navigator_platform": self.nav_platform,
                "navigator_user_agent": self.nav_user_agent,
                "languages": list(self.languages),
                "runOnInsecureOrigins": self.runOnInsecureOrigins,
            }
        )
        yield f"const opts = {opts}"
        yield self.skills.utils
        yield self.skills.generate_magic_arrays
        yield self.skills.navigator_hardware_concurrency

        if self.chrome_app:
            yield self.skills.chrome_app
        if self.chrome_csi:
            yield self.skills.chrome_csi
        if self.chrome_hairline:
            yield self.skills.chrome_hairline
        if self.chrome_load_times:
            yield self.skills.chrome_load_times
        if self.chrome_runtime:
            yield self.skills.chrome_runtime
        if self.iframe_content_window:
            yield self.skills.iframe_content_window
        if self.media_codecs:
            yield self.skills.media_codecs
        if self.navigator_languages:
            yield self.skills.navigator_languages
        if self.navigator_permissions:
            yield self.skills.navigator_permissions
        if self.navigator_platform:
            yield self.skills.navigator_platform
        if self.navigator_plugins:
            yield self.skills.navigator_plugins
        if self.navigator_vendor:
            yield self.skills.navigator_vendor
        if self.sourceurl:
            yield self.skills.sourceurl
        if self.webgl_vendor:
            yield self.skills.webgl_vendor
        if self.window_outerdimensions:
            yield self.skills.window_outerdimensions
        if self.patch_headless:
            yield self.skills.webdriver
            yield self.skills.navigator_user_agent


def stealth_sync(context: SyncContext, config: typing.Optional[NinjaConfig] = None):
    for feature in (config or NinjaConfig()).enabled_features:
        context.add_init_script(feature)


async def steal_playwright_async(
    context: ASyncContext, config: typing.Optional[NinjaConfig] = None
):
    for feature in (config or NinjaConfig()).enabled_features:
        await context.add_init_script(feature)


def fire(
    container: typing.Callable[[SyncContext], None],
    path_state: str,
    headless: typing.Optional[bool] = False,
):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # 可以使用持久化上下文處理 MFA 問題
        context = browser.new_context(
            locale="zh-CN", storage_state=path_state if os.path.isfile(path_state) else None
        )
        stealth_sync(context)
        container(context)
        context.storage_state(path=path_state)
        context.close()
        browser.close()
