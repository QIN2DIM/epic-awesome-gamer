#FROM amazonlinux:latest as builder
#
#WORKDIR /home/epic
#
#RUN yum update -y \
#    && yum install -y python3 wget
#
#COPY requirements.txt ./
#RUN pip3 install --no-cache-dir -r requirements.txt
#
#COPY src ./
#RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm \
#    && yum localinstall -y google-chrome-stable_current_x86_64.rpm \
#    && rm google-chrome-stable_current_x86_64.rpm \
#    && wget -P model/ https://github.com/QIN2DIM/hcaptcha-challenger/releases/download/model/yolov5n6.onnx
#

FROM python:3.10-slim as builder

WORKDIR /home/epic

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN apt update -y \
    && apt install -y wget

COPY src ./
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt install -y ./google-chrome-stable_current_amd64.deb \
    && rm ./google-chrome-stable_current_amd64.deb \
    && wget -P model/ https://github.com/QIN2DIM/hcaptcha-challenger/releases/download/model/yolov5n6.onnx \
    && wget -P model/ https://github.com/QIN2DIM/hcaptcha-challenger/releases/download/model/rainbow.yaml
