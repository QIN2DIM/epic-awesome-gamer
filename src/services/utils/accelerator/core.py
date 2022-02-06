# -*- coding: utf-8 -*-
# Time       : 2021/12/22 9:05
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os

import gevent
from gevent.queue import Queue


class CoroutineSpeedup:
    """轻量化的协程控件"""

    def __init__(self, docker=None, power: int = None):
        # 任务容器：queue
        self.worker, self.done = Queue(), Queue()

        # 任务容器
        self.docker = docker

        # 协程数
        self.power = max(os.cpu_count(), 2) if power is None else power

        # 任务队列满载时刻长度
        self.max_queue_size = 0

    def progress(self) -> str:
        """
        任务进度

        :return:
        """
        p = self.max_queue_size - self.worker.qsize()
        return "__pending__" if p < self.power else f"{p}/{self.max_queue_size}"

    def launcher(self, *args, **kwargs):
        """
        适配器实例生产

        :return:
        """
        while not self.worker.empty():
            task = self.worker.get_nowait()
            self.control_driver(task, *args, **kwargs)

    def control_driver(self, task, *args, **kwargs):
        """
        默认逻辑

        :param task:
        :return:
        """
        raise ImportError

    def preload(self):
        """
        数据预处理

        :return:
        """
        pass

    def overload(self):
        """
        任务重载

        :return:
        """
        if self.docker:
            for task in self.docker:
                self.worker.put_nowait(task)
        self.max_queue_size = self.worker.qsize()

    def offload(self) -> list:
        """
        缓存卸载

        :return:
        """
        docker = []
        while not self.done.empty():
            docker.append(self.done.get())
        return docker

    def killer(self):
        """
        缓存回收

        :return:
        """
        pass

    def go(self, power: int = None, *args, **kwargs):
        """
        框架接口

        :return:
        """

        # 任务重载
        self.overload()

        # 弹出空载任务
        if self.max_queue_size == 0:
            return

        self.power = self.power if power is None else power
        self.power = (
            self.max_queue_size if self.power > self.max_queue_size else self.power
        )

        # 任务启动
        task_list = []
        for _ in range(self.power):
            task = gevent.spawn(self.launcher, *args, **kwargs)
            task_list.append(task)
        try:
            gevent.joinall(task_list)
        finally:
            self.killer()
