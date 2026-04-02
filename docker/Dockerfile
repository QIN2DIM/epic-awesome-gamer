FROM mcr.microsoft.com/playwright:v1.52.0-noble
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

WORKDIR /app

SHELL ["/bin/bash", "-c"]

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG ALL_PROXY
ARG NO_PROXY

ENV DISPLAY=:99 \
    UV_LINK_MODE=copy \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    ALL_PROXY=${ALL_PROXY} \
    NO_PROXY=${NO_PROXY}

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-cache --all-extras

# Install system packages, including unzip for the manual installation
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    wget \
    curl \
    unzip && \
    rm -rf /var/lib/apt/lists/*

# Fetching addons and other necessary data.
# This will detect the pre-installed binaries and skip re-downloading them.
RUN uv run camoufox fetch

ADD . /app
