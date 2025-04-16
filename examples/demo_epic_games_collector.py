import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, ViewportSize

from epic_awesome_gamer.collector import startup_epic_awesome_gamer


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="tmp/.cache/user_data",
            record_video_dir=Path("tmp/.cache/record"),
            record_video_size=ViewportSize(width=1920, height=1080),
            headless=False,
            locale="en-US",
        )

        await startup_epic_awesome_gamer(context)


if __name__ == "__main__":
    asyncio.run(main())
