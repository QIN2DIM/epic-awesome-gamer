import requests
import os
token = os.environ['TOKEN']
title= 'Epic-FreeGamer'
content ='Epic-FreeGamer任务已执行'
url = 'http://www.pushplus.plus/send?token='+token+'&title='+title+'&content='+content
requests.get(url)
