# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:15
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :
"""
import os
from pathlib import Path

from hcaptcha_challenger.agent import AgentConfig
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT.joinpath("logs")
USER_DATA_DIR = PROJECT_ROOT.joinpath("user_data")


class EpicSettings(AgentConfig):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    EPIC_EMAIL: str = Field(
        default_factory=lambda: os.getenv("EPIC_EMAIL"),
        description="Epic 游戏账号，需要关闭多步验证",
    )

    EPIC_PASSWORD: SecretStr = Field(
        default_factory=lambda: os.getenv("EPIC_PASSWORD"),
        description=" Epic 游戏密码，需要关闭多步验证",
    )

    DISABLE_BEZIER_TRAJECTORY: bool = Field(
        default=True, description="是否启用贝塞尔曲线轨迹模拟，默认关闭，直接使用 Camoufox 的特性"
    )

    # APPRISE_SERVERS: str | None = Field(
    #     default="", description="System notification by Apprise\nhttps://github.com/caronc/apprise"
    # )
