import os
import re
import time

import requests
from loguru import logger
from selenium.common.exceptions import (
    ElementNotVisibleException,
    ElementClickInterceptedException,
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from undetected_chromedriver import Chrome

from .exceptions import LabelNotFoundException, ChallengeReset, ChallengeTimeout


class ArmorCaptcha:
    """hCAPTCHA challenge 驱动控制"""

    def __init__(self, dir_workspace: str = None, debug=False):

        self.action_name = "ArmorCaptcha"
        self.debug = debug

        # 存储挑战图片的目录
        self.runtime_workspace = ""

        # 博大精深！
        self.label_alias = {
            "自行车": "bicycle",
            "火车": "train",
            "卡车": "truck",
            "公交车": "bus",
            "巴土": "bus",
            "巴士": "bus",
            "飞机": "aeroplane",
            "ー条船": "boat",
            "船": "boat",
            "汽车": "car",
            "摩托车": "motorbike",
            "垂直河流": "vertical river",
            "天空中向左飞行的飞机": "airplane in the sky flying left",
            "请选择天空中所有向右飞行的飞机": "airplanes in the sky that are flying to the right",
        }

        # 样本标签映射 {挑战图片1: locator1, ...}
        self.alias2locator = {}
        # 填充下载链接映射 {挑战图片1: url1, ...}
        self.alias2url = {}
        # 填充挑战图片的缓存地址 {挑战图片1: "/images/挑战图片1.png", ...}
        self.alias2path = {}
        # 存储模型分类结果 {挑战图片1: bool, ...}
        self.alias2answer = {}
        # 图像标签
        self.label = ""
        # 运行缓存
        self.dir_workspace = dir_workspace if dir_workspace else "."

        self._headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62"
        }

    def log(self, message: str, **params) -> None:
        """格式化日志信息"""
        if not self.debug:
            return

        motive = "Challenge"
        flag_ = f">> {motive} [{self.action_name}] {message}"
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])
        logger.debug(flag_)

    def _init_workspace(self):
        """初始化工作目录，存放缓存的挑战图片"""
        _prefix = f"{int(time.time())}" + f"_{self.label}" if self.label else ""
        _workspace = os.path.join(self.dir_workspace, _prefix)
        if not os.path.exists(_workspace):
            os.mkdir(_workspace)
        return _workspace

    def tactical_retreat(self) -> bool:
        """模型存在泛化死角，遇到指定标签时主动进入下一轮挑战，节约时间"""
        if self.label in ["水上飞机"] or not self.label_alias.get(self.label):
            self.log(message="模型泛化较差，逃逸", label=self.label)
            return True
        return False

    def mark_samples(self, ctx: Chrome):
        """
        获取每个挑战图片的下载链接以及网页元素位置

        :param ctx:
        :return:
        """
        self.log(message="获取挑战图片链接及元素定位器")

        # 等待图片加载完成
        WebDriverWait(ctx, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@class='task-image']"))
        )
        time.sleep(1)

        # DOM 定位元素
        samples = ctx.find_elements(By.XPATH, "//div[@class='task-image']")
        for sample in samples:
            alias = sample.get_attribute("aria-label")
            while True:
                try:
                    image_style = sample.find_element(
                        By.CLASS_NAME, "image"
                    ).get_attribute("style")
                    url = re.split(r'[(")]', image_style)[2]
                    self.alias2url.update({alias: url})
                    break
                except IndexError:
                    continue
            self.alias2locator.update({alias: sample})

    def get_label(self, ctx: Chrome):
        """
        获取人机挑战需要识别的图片类型（标签）

        :param ctx:
        :return:
        """
        try:
            label_obj = WebDriverWait(
                ctx, 30, ignored_exceptions=ElementNotVisibleException
            ).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='prompt-text']"))
            )
        except TimeoutException:
            raise ChallengeReset("人机挑战意外通过")
        try:
            if "包含" in label_obj.text:
                _label = re.split(r"[包含 图片]", label_obj.text)[2][:-1]
            else:
                _label = label_obj.text
        except (AttributeError, IndexError):
            raise LabelNotFoundException("获取到异常的标签对象。")
        else:
            self.label = _label
            self.log(
                message="获取挑战标签",
                label=f"{self.label}({self.label_alias.get(self.label, 'none')})",
            )

    def download_images(self):
        """
        下载挑战图片

        ### hcaptcha 设有挑战时长的限制

          如果一段时间内没有操作页面元素，<iframe> 框体就会消失，之前获取的 Element Locator 将过时。
          需要借助一些现代化的方法尽可能地缩短 `获取数据集` 的耗时。

        ### 解决方案

        1. 使用基于协程的方法拉取图片到本地，最佳实践（本方法）。拉取效率比遍历下载提升至少 10 倍。
        2. 截屏切割，有一定的编码难度。直接截取目标区域的九张图片，使用工具函数切割后识别。需要自己编织定位器索引。

        :return:
        """
        _workspace = self._init_workspace()
        for alias, url in self.alias2url.items():
            path_challenge_img = os.path.join(_workspace, f"{alias}.png")
            stream = requests.get(url).content
            with open(path_challenge_img, "wb") as file:
                file.write(stream)

    def challenge(self, ctx: Chrome, model):
        """
        图像分类，元素点击，答案提交

        ### 性能瓶颈

        此部分图像分类基于 CPU 运行。如果服务器资源极其紧张，图像分类任务可能无法按时完成。
        根据实验结论来看，如果运行时内存少于 512MB，且仅有一个逻辑线程的话，基本上是与深度学习无缘了。

        ### 优雅永不过时

        `hCaptcha` 的挑战难度与 `reCaptcha v2` 不在一个级别。
        这里只要正确率上去就行，也即正确图片覆盖更多，通过率越高（即使因此多点了几个干扰项也无妨）。
        所以这里要将置信度尽可能地调低（未经针对训练的模型本来就是用来猜的）。

        :return:
        """
        self.log(message="开始挑战")

        # {{< IMAGE CLASSIFICATION >}}
        ta = []
        for alias, img_filepath in self.alias2path.items():
            # 读取二进制数据编织成模型可接受的类型
            with open(img_filepath, "rb") as file:
                data = file.read()

            # 获取识别结果
            t0 = time.time()
            result = model.solution(img_stream=data, label=self.label_alias[self.label])
            ta.append(time.time() - t0)

            # 模型会根据置信度给出图片中的多个目标，只要命中一个就算通过
            if result:
                # 选中标签元素
                try:
                    self.alias2locator[alias].click()
                except WebDriverException:
                    pass

        # {{< SUBMIT ANSWER >}}
        try:
            WebDriverWait(
                ctx, 35, ignored_exceptions=ElementClickInterceptedException
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//div[@class='button-submit button']")
                )
            ).click()
        except (TimeoutException, ElementClickInterceptedException):
            raise ChallengeTimeout("CPU 算力不足，无法在规定时间内完成挑战")

        self.log(message=f"提交挑战 {model.flag}: {round(sum(ta), 2)}s")

    def challenge_success(self, ctx: Chrome, init: bool = True, **kwargs):
        """
        自定义的人机挑战通过逻辑

        :return:
        """
        raise NotImplementedError

    def anti_captcha(self):
        """
        自定义的人机挑战触发逻辑

        具体思路是：
        1. 进入 hcaptcha iframe
        2. 获取图像标签
            需要加入判断，有时候 `hcaptcha` 计算的威胁程度极低，会直接让你过，
            于是图像标签之类的元素都不会加载在网页上。
        3. 获取各个挑战图片的下载链接及网页元素位置
        4. 图片下载，分类
            需要用一些技术手段缩短这部分操作的耗时。人机挑战有时间限制。
        5. 对正确的图片进行点击
        6. 提交答案
        7. 判断挑战是否成功
            一般情况下 `hcaptcha` 的验证有两轮，
            而 `recaptcha vc2` 之类的人机挑战就说不准了，可能程序一晚上都在“循环”。
        :return:
        """
