# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:27
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:

import os
import shlex


def shell_echo(cmd: str, mode="default"):
    """
    为输出安全做的协调函数
    :param cmd:
    :param mode:
    :return:
    """
    if mode == "default":
        return os.system(cmd)
    if mode == "safe":
        return os.system(shlex.quote(cmd))


def set_ubuntu_dev():
    shell_echo("apt-get update && apt-get install -y gcc wget unzip")


def set_google_chrome(force=False):
    # Google-chrome already exists in the current environment
    if shell_echo("google-chrome --version") == 0:
        # uninstall command
        if force:
            os.system("sudo rpm -e google-chrome-stable")
        return True

    # installing Google Chrome on Ubuntu
    shell_echo(
        "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb >/dev/null"
    )
    shell_echo(
        "apt install ./google-chrome-stable_current_amd64.deb -y >/dev/null"
    )


def init_project():
    print("---> Remove irrelevant information")
    shell_echo("rm -rf chromedriver_linux64.zip")
    shell_echo("rm -rf google-chrome-stable_current_x86_64.rpm")
    shell_echo("clear")


def build(force: bool = False):
    set_ubuntu_dev()
    set_google_chrome(force)
    init_project()


if __name__ == "__main__":
    build()
