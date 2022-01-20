import os
import re
import time
import urllib.request

import cv2
import numpy as np
import requests
from loguru import logger
from selenium.common.exceptions import (
    NoSuchElementException, ElementNotVisibleException,
    ElementClickInterceptedException, WebDriverException, TimeoutException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from undetected_chromedriver import Chrome

from .exceptions import LabelNotFoundException, ChallengeReset


class ArmorCaptcha:
    def __init__(self, dir_workspace: str = None, debug=False):

        self.action_name = "ArmorCaptcha"
        self.debug = debug

        # 存储挑战图片的目录
        self.runtime_workspace = ""

        # 徒增功耗
        self.label_alias = {
            "自行车": "bicycle",
            "火车": "train",
            "卡车": "truck",
            "公交车": "bus",
            "飞机": "airplane",
            "ー条船": "boat",
            "汽车": "car",
            "摩托车": "motorcycle",
            "雨伞": "umbrella",
        }

        # 样本标签映射 {挑战图片1: locator1, ...}
        self.alias2locator = {}
        # 填充下载链接映射 {挑战图片1: url1, ...}
        self.alias2url = {}
        # 填充挑战图片的缓存地址 {挑战图片1: "/images/挑战图片1.png", ...}
        self.alias2path = {}
        # 图像标签
        self.label = ""
        # 运行缓存
        self.dir_workspace = dir_workspace if dir_workspace else "."

        self._headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62",
        }

    def log(self, message: str = "", **params):
        motive = "Challenge"
        flag_ = ">> {} [{}]".format(motive, self.action_name)
        if message != "":
            flag_ += " {}".format(message)
        if params:
            flag_ += " - "
            flag_ += " ".join([f"{i[0]}={i[1]}" for i in params.items()])
        if self.debug:
            return logger.debug(flag_)

    @staticmethod
    def _unused_download_armor(api: Chrome):
        """
        弃用。

        :param api:
        :return:
        """
        api.get("https://greasyfork.org/zh-CN/scripts/425854-hcaptcha-solver-automatically-solves-hcaptcha-in-browser")

        download_link = WebDriverWait(api, 10, poll_frequency=0.5, ignored_exceptions=NoSuchElementException).until(
            EC.presence_of_element_located((By.CLASS_NAME, "install-link"))
        ).get_attribute("href")

        _handle_num = len(api.window_handles)

        # 自动开启一个新的 tab
        api.get(download_link)

        while len(api.window_handles) == _handle_num:
            pass

        api.switch_to.window(api.window_handles[-1])

        WebDriverWait(api, 30, poll_frequency=0.5, ignored_exceptions=NoSuchElementException).until(
            EC.element_to_be_clickable((By.NAME, "安装"))
        ).click()

        # 回到主任务标签
        api.switch_to.window(api.window_handles[0])

    def _init_workspace(self):
        _prefix = "{}{}".format(
            int(time.time()),
            f'_{self.label}' if self.label else ''
        )
        _workspace = os.path.join(self.dir_workspace, _prefix)
        if not os.path.exists(_workspace):
            os.mkdir(_workspace)
        return _workspace

    def tactical_retreat(self):
        """
        # 模型泛化不足，快逃。

        :return:
        """
        if self.label in ["摩托车", ] or not self.label_alias.get(self.label):
            self.log(message="模型泛化较差，逃逸", label=self.label)
            return True

    def mark_samples(self, api: Chrome):
        self.log(message="获取挑战图片链接及元素定位器")

        # 等待图片加载完成
        WebDriverWait(api, 10, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@class='task-image']"))
        )
        time.sleep(1)

        # DOM 定位元素
        samples = api.find_elements(By.XPATH, "//div[@class='task-image']")
        for sample in samples:
            alias = sample.get_attribute("aria-label")
            # TODO 加入超时判定
            while True:
                try:
                    image_style = sample.find_element(By.CLASS_NAME, "image").get_attribute("style")
                    url = re.split(r'[(")]', image_style)[2]
                    self.alias2url.update({alias: url})
                    break
                except IndexError:
                    continue
            self.alias2locator.update({alias: sample})

    def get_label(self, api: Chrome):
        label_obj = WebDriverWait(api, 30, ignored_exceptions=ElementNotVisibleException).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='prompt-text']"))
        )
        try:
            _label = re.split(r"[包含 的]", label_obj.text)[2]
        except (AttributeError, IndexError):
            raise LabelNotFoundException("获取到异常的标签对象。")
        else:
            self.label = _label
            self.log(
                message="获取挑战标签",
                label=f"{self.label}({self.label_alias.get(self.label, 'none')})"
            )

    def download_images(self):
        _workspace = self._init_workspace()
        for alias, url in self.alias2url.items():
            path_challenge_img = os.path.join(_workspace, f"{alias}.png")
            urllib.request.urlretrieve(url, path_challenge_img)

    def image_classifier(self):
        raise NotImplementedError

    def challenge(self, api: Chrome, correct_samples: list, ):
        # 点击认为是的拼图元素
        for sample in correct_samples:
            self.alias2locator[sample].click()
        # 提交答案
        WebDriverWait(api, 35, ignored_exceptions=ElementClickInterceptedException).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@class='button-submit button']"))
        ).click()

        self.log(message="提交挑战")

    def _challenge_success(self, api: Chrome, init: bool = True):
        _challenge_ok = 1

        # index == 0
        # 经过一轮识别点击后，出现三种结果
        # - 通过验证（极少）
        # - 第二轮（极大）
        #   通过短时间内可否继续点击拼图来断言是否陷入第二轮测试
        # - 直接 Error（极小）
        #   根据当前DOM树是否刷新出警告信息判断
        flag = api.current_url
        if init:
            try:
                WebDriverWait(api, 2, ignored_exceptions=WebDriverException).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@class='task-image']"))
                )
            except TimeoutException:
                pass
            else:
                self.log("挑战继续")
                return False

        try:
            challenge_reset = WebDriverWait(api, 5, ignored_exceptions=WebDriverException).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='MuiAlert-message']"))
            )
        except TimeoutException:
            try:
                WebDriverWait(api, 8).until(EC.url_changes(flag))
            except TimeoutException:
                self.log("断言超时，挑战继续")
                return False
            else:
                self.log("挑战成功")
                return True
        else:
            self.log("挑战失败，需要重置挑战")
            challenge_reset.click()
            raise ChallengeReset


class YOLO:
    def __init__(self, dir_model):
        self.dir_model = "./model" if dir_model is None else dir_model
        self.cfg = {
            "name": "model_configuration",
            "path": os.path.join(self.dir_model, "yolov4_new.cfg"),
            "src": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4_new.cfg"
        }
        self.weights = {
            "name": "model_weights",
            "path": os.path.join(self.dir_model, "yolov4_new.weights"),
            "src": "https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4_new.weights"
        }

        self.classes = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
                        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
                        "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
                        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
                        "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
                        "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
                        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
                        "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
                        "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
                        "teddy bear", "hair drier", "toothbrush"]

    def download_model(self):
        if not os.path.exists(self.dir_model):  # noqa
            os.mkdir(self.dir_model)

        for dm in [self.cfg, self.weights]:
            if os.path.exists(dm["path"]):
                continue
            print(f"Downloading {dm['name']} from {dm['src']}")

            try:
                r = requests.get(dm["src"], allow_redirects=True, stream=True)
            except requests.exceptions.RequestException:
                return None
            else:
                with open(dm["path"], "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        f.write(chunk)

    def detect_common_objects(self, img_stream, confidence=0.28, nms_thresh=0.4):
        np_array = np.frombuffer(img_stream, np.uint8)
        img = cv2.imdecode(np_array, flags=1)
        height, width = img.shape[:2]

        blob = cv2.dnn.blobFromImage(img, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        self.download_model()

        net = cv2.dnn.readNetFromDarknet(self.cfg["path"], self.weights["path"])

        net.setInput(blob)

        layer_names = net.getLayerNames()
        output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
        outs = net.forward(output_layers)

        class_ids = []
        confidences = []
        boxes = []

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                max_conf = scores[class_id]
                if max_conf > confidence:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = center_x - (w / 2)
                    y = center_y - (h / 2)
                    class_ids.append(class_id)
                    confidences.append(float(max_conf))
                    boxes.append([x, y, w, h])

        indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence, nms_thresh)

        bbox = []
        label = []
        conf = []

        for i in indices:
            i = i[0]
            box = boxes[i]
            x = box[0]
            y = box[1]
            w = box[2]
            h = box[3]
            bbox.append([int(x), int(y), int(x + w), int(y + h)])
            label.append(str(self.classes[class_ids[i]]))
            conf.append(confidences[i])

        return bbox, label, conf
