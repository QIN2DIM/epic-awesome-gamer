# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from gevent import monkey

monkey.patch_all()

from apis.scaffold import get, challenge, install


class Scaffold:
    NotImplementedErrorWarning = "本指令功能暂未完成，敬请期待。"

    def __init__(self):
        pass

    @staticmethod
    def install(cdn: bool = False):
        """
        下载项目运行所需的配置。

        ## Basic Usage

        Usage: python main.py install
        _________________________________________________________________
        or: python main.py install --cdn       |使用CDN下载模型
        _________________________________________________________________

        ## Intro

        本指令不拉取 `requirements.txt`，需要手动操作。

        ## Warning

        - 本指令仍有较大进步空间（在测试中...）
            - 若小伙伴使用此指令后并不能一次性将所有依赖拉取完毕，出现缺漏，可以将相关信息提交至 `issues`。
            - 若下载速度较慢，可以使用 `cdn` 参数加速下载
        - https://github.com/QIN2DIM/epic-awesome-gamer

        :param cdn: CloudFlare CDN
        :return:
        """
        install.run(cdn=cdn)

    @staticmethod
    def get(debug: bool = False):
        """
        获取 Epic Store 所有未在库的免费游戏。一键操作，将免费商城搬空，科技改变生活！

        ## Local Static CacheFile

        - 考虑到 `get` 是玩家手动执行的指令，而 Epic 更新免费游戏的频率并不高，所以复用本地静态缓存是比较合理的打开方式。
        - 此指令会将 Epic 当前的免费游戏的展示链接存储在 `src/database/explorer` 目录下。

        ## Warning

        - 本指令仍有较大进步空间（在测试中...）
            - 若小伙伴在首轮中执行中遇到 `QUIT` 异常（几乎必然），可以在执行结束再执行几轮 `get` 指令，直至清空商城；
                - 有些异常是仅在性能释放不足时被抛出，在单例执行时几乎不会撞见。
                - 因权限无法获取的游戏需要玩家手动操作，如“成人内容”“地区或平台限制”
        - 若出现其他报错，请留意 Exception 信息，并将完整的栈追踪信息提交至 `issues` ，不胜感激！
        -  https://github.com/QIN2DIM/epic-awesome-gamer

        :param debug: 显示栈追踪日志信息
        :return:
        """
        get.join(trace=debug)

    @staticmethod
    def challenge():
        """
        正面硬刚人机验证，为当前账号获取有效的身份令牌。

        ## Intro

        - 请确保你已在 `config.yaml` 中配置了正确的账号信息。
        - 本指令可插入在项目 `uminoleon/epicgames-claimer` 的生产环节之中，用于被动更新玩家的身份令牌。
        - 更新后的 cookie 明文信息将存储到 `/src/database/cookies/user_cookies.txt` 中

        ## Tips

        - 本指令并不会强制激活人机验证。硬刚人机挑战不是目的，获取到有效的身份令牌才是目的，不要徒增功耗。
        - 也即，如果当前缓存的身份令牌还未失效，任务跳过。
        - 请无视 `SurpriseExit()` 异常

        :return:
        """
        challenge.run()

        """
        [🌀] 优雅离场
        _______________
        脑洞大开的作者想挑战一下 Python 自带的垃圾回收机制，
        决定以一种极其垂直的方式结束系统任务。
        """
        import sys
        sys.exit()
        # raise SurpriseExit("优雅离场")

    @staticmethod
    def deploy():
        """
        部署系统定时任务。

        :return:
        """
        # service.SystemCrontab()
        raise NotImplementedError(Scaffold.NotImplementedErrorWarning)

    @staticmethod
    def ping():
        """
        测试配置文件中的账号信息是否有效。

        :return:
        """
        raise NotImplementedError(Scaffold.NotImplementedErrorWarning)

    @staticmethod
    def config():
        """
        提供一个 WEBUI 引导输入，更新配置文件。

        :return:
        """
        raise NotImplementedError(Scaffold.NotImplementedErrorWarning)

    @staticmethod
    def clear():
        """
        安全清理系统运行缓存

        安全清理人机验证，运行日志等临时缓存。
        :return:
        """
        raise NotImplementedError(Scaffold.NotImplementedErrorWarning)
