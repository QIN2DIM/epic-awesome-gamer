# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:

# OrderHistory Object

# FreeGames Object

# 1. 初始化数据库
# Format: {email2token}.yaml
# 条件：空（路径/文件）超时（一周一更）
# 特性：携带 cookies，不同地区 frees 略有不同
# 参数：允许强制更新
# 功耗：order 10items/page frees 40items/page，需要 (2 + int(total / 10) + 1)
"""
# database/explorer/test.yaml

order:
    namespace1:
    namespace2:
    namespace3:
frees:
    namespace1:
    namespace2:
    namespace3:
"""

# 2. 更新数据库
# 内容：更新 orders， 更新 frees
