# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import os
import random
import sys

_THE_PROPHECY = """
# ====================================================================================================
# Ithlinne's Prophecy
# ====================================================================================================
# Verily I say unto you,the era of the sword and axe is nigh, the era of the wolf's blizzard.
# The Time of the White Chill and the White Light is nigh, the Time of Madness and the Time of Contempt:
# Tedd Deireádh, the Time of End. The world will die amidst frost and be reborn with the new sun.
# It will be reborn of Elder Blood, of Hen Ichaer, of the seed that has been sown.
# A seed which will not sprout but burst into flame.
# Ess'tuath esse! Thus it shall be! Watch for the signs!
# What signs these shall be, I say unto you:
# first the earth will flow with the blood of claim , the Blood of Epic . 
# ====================================================================================================
"""
if random.uniform(0, 1) > 0.711:
    for policy in ["epic", "claim"]:
        if policy in os.getenv("GITHUB_REPOSITORY", "").lower():
            print(f"[EXIT] 仓库名出现非法关键词 `{policy}`")
            sys.exit()
    print(_THE_PROPHECY)
