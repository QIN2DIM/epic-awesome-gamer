# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from selenium.common.exceptions import WebDriverException

from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger
from services.utils import CoroutineSpeedup, ToolBox

SILENCE = True

bricklayer = Bricklayer(silence=SILENCE)
explorer = Explorer(silence=SILENCE)


class SpawnBooster(CoroutineSpeedup):
    def __init__(self, docker=None, power: int = 4):
        super(SpawnBooster, self).__init__(docker=docker, power=power)

    def control_driver(self, context, *args, **kwargs):
        ctx_cookies, url = context
        response = explorer.is_my_game(ctx_cookies=ctx_cookies, page_link=url)

        # 启动 Bricklayer，获取免费游戏
        if response is False:
            logger.debug(ToolBox.runtime_report(
                motive="BUILD",
                action_name="SpawnBooster",
                message="正在为玩家获取免费游戏",
                progress=f"[{self.progress()}]",
                url=url
            ))
            try:
                bricklayer.get_free_game(ctx_cookies=ctx_cookies, page_link=url, refresh=False)
            except WebDriverException as e:
                logger.exception(e)
                logger.error(ToolBox.runtime_report(
                    motive="QUIT",
                    action_name="SpawnBooster",
                    message="游戏获取失败",
                    progress=f"[{self.progress()}]",
                    url=url
                ))


def join(update: bool = None):
    """
    科技改变生活，一键操作，将免费商城搬空！

    :param update: 强制更新换存在本地的免费游戏列表
    :return:
    """
    logger.debug(ToolBox.runtime_report(
        motive="BUILD",
        action_name="EpicGamer",
        message="正在为玩家订阅免费游戏"
    ))

    """
    [🔨] 读取有效的玩家身份令牌
    _______________
    - 此处以 `api_cookies.txt` 为准，仅当身份令牌无效时才会使用 
    `config.yaml` 中的账号信息重置身份令牌。
    """
    bricklayer.cookie_manager.refresh_ctx_cookies(verify=True)
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    """
    [🔨] 更新商城的免费游戏
    _______________
    """
    if update is not True:
        urls = explorer.load_game_objs(only_url=True)
        if not urls:
            explorer.discovery_free_games(ctx_cookies=ctx_cookies, save=True)
    else:
        explorer.discovery_free_games(ctx_cookies=ctx_cookies, save=True)
        urls = explorer.load_game_objs(only_url=True)

    """
    [🔨] 启动 Bricklayer，获取免费游戏
    _______________
    - 启动一轮协程任务，执行效率受限于本地网络带宽，若首轮报错频发请手动调低 `power` 参数。
    - 如果在命令行操作系统上运行本指令，执行效率受限于硬件性能。
    """
    docker = [[ctx_cookies, url] for url in urls]
    SpawnBooster(docker=docker, power=4).go()
