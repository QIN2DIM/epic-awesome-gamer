import requests
token = os.environ['TOKEN']
title= 'Epic-FreeGamer'
content ='执行成功'
url = 'http://www.pushplus.plus/send?token='+token+'&title='+title+'&content='+content
requests.get(url)