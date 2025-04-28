FROM python:3.12

WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    libgl1-mesa-glx \
    libglib2.0-0 \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 复制项目文件
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 创建虚拟环境并安装依赖
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install -e .

# 获取数据
RUN . /app/.venv/bin/activate && \
    uv run playwright install firefox --with-deps && \
    uv run camoufox fetch

# 设置入口点
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/bin/bash", "-c", "source /app/.venv/bin/activate && uv run xvfb-run --server-args='-screen 0 1920x1080x24' epic collect"]
