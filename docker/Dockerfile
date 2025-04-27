FROM mcr.microsoft.com/playwright:v1.52.0-noble

WORKDIR /app

# Install system dependencies
RUN apt update && apt install -y xvfb tini

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies using uv
RUN uv venv && uv pip install -U epic-awesome-gamer

# Fetch data using camoufox
RUN uv run camoufox fetch
