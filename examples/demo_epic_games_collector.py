import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, ViewportSize, BrowserContext

from epic_awesome_gamer.collector import EpicAgent


async def startup_epic_awesome_gamer(context: BrowserContext):
    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    agent = EpicAgent(page)

    await agent.collect_epic_games()


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
