# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/20 08:10
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    : Celery application configuration
"""

from celery import Celery
from celery.schedules import crontab

from settings import settings


def init_app():
    # Create Celery app instance
    celery_app = Celery("epic-awesome-gamer", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

    # Configure Celery
    celery_app.conf.update(
        timezone="UTC",
        enable_utc=True,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1,
        task_track_started=True,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=True,
        worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    )

    imports = ["schedule.epic_collect_games_task"]
    beat_schedule = {
        "epic_collect_games_task": {
            "task": "schedule.epic_collect_games_task.epic_collect_games_task",
            "schedule": crontab("1 */5 * * *"),
        }
    }
    celery_app.conf.update(beat_schedule=beat_schedule, imports=imports)

    # Import tasks to register them
    return celery_app


ext_celery_app = init_app()
