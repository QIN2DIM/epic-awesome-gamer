# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Epic 免费人 (Epic Awesome Gamer) is a Python automation tool that gracefully claims weekly free games from the Epic Games Store. It uses browser automation with Playwright and includes an AI-powered hCaptcha solver using the `hcaptcha-challenger` library.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv (recommended)
uv sync

# Alternative: install dev dependencies
uv sync --group dev
```

### Code Quality
```bash
# Format code with Black
uv run black . -C -l 100

# Lint with Ruff
uv run ruff check --fix
```

## Architecture

### Core Components

- **`app/models.py`**: Pydantic models for Epic Games data structures (OrderItem, Order, PromotionGame)
- **`app/settings.py`**: Configuration management using pydantic-settings, extends hcaptcha-challenger's AgentConfig
- **`app/services/epic_games_service.py`**: Main game collection logic and Epic Store interaction
- **`app/services/epic_authorization_service.py`**: Authentication and login handling
- **`app/jobs.py`**: Job orchestration functions for collecting and adding games to cart
- **`app/deploy.py`**: Main deployment/execution entry point

### Key Dependencies

- **hcaptcha-challenger[camoufox]**: AI-powered captcha solving with Camoufox browser
- **playwright**: Browser automation framework
- **pydantic-settings**: Configuration management with environment variable support
- **apscheduler**: Task scheduling for automated runs

### Directory Structure

- `app/logs/`: Application logs (error.log, runtime.log, serialize.log)
- `app/runtime/`: Runtime data including screenshots, recordings, and hcaptcha cache
- `app/user_data/`: Browser profile and session data
- `docker/`: Docker compose configuration and environment files

### Configuration

Environment variables are managed through `EpicSettings` class in `settings.py`:

- `EPIC_EMAIL`: Epic Games account email (2FA must be disabled)
- `EPIC_PASSWORD`: Epic Games account password
- `GEMINI_API_KEY`: Google Gemini API key for captcha solving
- `CRON_SCHEDULE`: Cron expression for scheduled runs (default: every 5 hours)

### Browser Automation Flow

1. Initialize Epic agent with Playwright page
2. Handle authentication via `EpicAuthorization`
3. Fetch promotions from Epic Games API
4. Navigate to game pages and add free games to cart
5. Handle any hCaptcha challenges using AI solver
6. Complete checkout process

## Testing

Test execution is not allowed.

## Development Notes
