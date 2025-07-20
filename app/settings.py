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
VOLUMES_DIR = PROJECT_ROOT.joinpath("volumes")

LOG_DIR = VOLUMES_DIR.joinpath("logs")
USER_DATA_DIR = VOLUMES_DIR.joinpath("user_data")

RUNTIME_DIR = VOLUMES_DIR.joinpath("runtime")
SCREENSHOTS_DIR = VOLUMES_DIR.joinpath("screenshots")
RECORD_DIR = VOLUMES_DIR.joinpath("record")
HCAPTCHA_DIR = VOLUMES_DIR.joinpath("hcaptcha")


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
        default=True, description="是否关闭贝塞尔曲线轨迹模拟，默认关闭，直接使用 Camoufox 的特性"
    )

    cache_dir: Path = HCAPTCHA_DIR.joinpath(".cache")
    challenge_dir: Path = HCAPTCHA_DIR.joinpath(".challenge")
    captcha_response_dir: Path = HCAPTCHA_DIR.joinpath(".captcha")

    ENABLE_APSCHEDULER: bool = Field(default=True, description="是否启用定时任务，默认启用")

    TASK_TIMEOUT_SECONDS: int = Field(
        default=900,  # 15 minutes
        description="Maximum execution time for browser tasks before force termination",
    )

    # Celery and Redis settings
    REDIS_URL: str = Field(
        default="redis://redis:6379/0", description="Redis URL for Celery broker and result backend"
    )

    CELERY_WORKER_CONCURRENCY: int = Field(
        default=1, description="Number of concurrent Celery workers"
    )

    CELERY_TASK_TIME_LIMIT: int = Field(
        default=1200,  # 20 minutes - slightly higher than TASK_TIMEOUT_SECONDS
        description="Celery task hard time limit in seconds",
    )

    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(
        default=900,  # 15 minutes - same as TASK_TIMEOUT_SECONDS
        description="Celery task soft time limit in seconds",
    )

    # APPRISE_SERVERS: str | None = Field(
    #     default="", description="System notification by Apprise\nhttps://github.com/caronc/apprise"
    # )

    @property
    def user_data_dir(self) -> Path:
        target_ = USER_DATA_DIR.joinpath(self.EPIC_EMAIL)
        if not target_.is_dir():
            target_.mkdir(parents=True, exist_ok=True)
        return target_


settings = EpicSettings()
settings.ignore_request_questions = ["Please drag the crossing to complete the lines"]
