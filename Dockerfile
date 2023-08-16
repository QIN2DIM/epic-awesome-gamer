FROM python:3.10 as builder

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN apt update -y \
    && apt install -y wget xvfb tini \
    && playwright install \
    && playwright install-deps firefox

WORKDIR /home/epic/src

COPY src ./