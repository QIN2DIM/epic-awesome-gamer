import asyncio
import sys
from pathlib import Path

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, ViewportSize

from epic_awesome_gamer import EpicSettings
from epic_awesome_gamer.collector import EpicAgent


async def startup_epic_awesome_gamer(page: Page):
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)

    await agent.collect_epic_games()


async def main():
    headless = "virtual" if sys.platform == "linux" else False
    user_data_dir = "tmp/.cache/epic_default_user"
    record_video_dir = Path("tmp/.cache/record")
    record_video_size = ViewportSize(width=1920, height=1080)

    async with AsyncCamoufox(
        persistent_context=True,
        from_options={
            "user_data_dir": user_data_dir,
            "record_video_dir": record_video_dir,
            "record_video_size": record_video_size,
        },
        screen=Screen(max_width=1920, max_height=1080),
        humanize=0.5,
        headless=headless,
    ) as browser:
        page = browser.pages[-1] if browser.pages else await browser.new_page()
        await startup_epic_awesome_gamer(page)


if __name__ == "__main__":
    asyncio.run(main())
