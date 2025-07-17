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

# Install system packages, including unzip for the manual installation
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    wget \
    curl \
    unzip && \
    rm -rf /var/lib/apt/lists/*

# Pre-install camoufox binaries to avoid GitHub API rate limits
# This step manually downloads and unzips the specified Camoufox version into the cache directory.
RUN CAMOUFOX_URL="https://github.com/daijro/camoufox/releases/download/v135.0.1-beta.24/camoufox-135.0.1-beta.24-lin.x86_64.zip" && \
    CAMOUFOX_DIR="/root/.cache/camoufox" && \
    mkdir -p ${CAMOUFOX_DIR} && \
    wget -qO /tmp/camoufox.zip "${CAMOUFOX_URL}" && \
    unzip -q /tmp/camoufox.zip -d ${CAMOUFOX_DIR} && \
    rm /tmp/camoufox.zip

# Fetching addons and other necessary data.
# This will detect the pre-installed binaries and skip re-downloading them.
RUN uv run camoufox fetch

ADD . /app