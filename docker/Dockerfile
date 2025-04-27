FROM mcr.microsoft.com/playwright:v1.52.0-noble as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt install -y curl libgl1-mesa-glx libglib2.0-0 wget xvfb tini \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set PATH to include uv
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies using uv
RUN uv pip install -U epic-awesome-gamer

# Fetch data using camoufox
RUN uv run camoufox fetch
