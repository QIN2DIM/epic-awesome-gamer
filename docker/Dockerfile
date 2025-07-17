FROM mcr.microsoft.com/playwright:v1.52.0-noble
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

WORKDIR /app

SHELL ["/bin/bash", "-c"]

ENV DISPLAY=:99 \
    UV_LINK_MODE=copy

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-cache --all-extras

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    wget \
    curl && \
    rm -rf /var/lib/apt/lists/*

ADD . /app
