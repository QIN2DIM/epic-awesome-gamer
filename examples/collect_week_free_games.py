import asyncio

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page

from epic_awesome_gamer import EpicSettings
from epic_awesome_gamer.collector import EpicAgent


async def startup_epic_awesome_gamer(page: Page):
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)

    await agent.collect_epic_games()


async def main():
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir="tmp/.cache/user_data",
        screen=Screen(max_width=1920, max_height=1080),
        humanize=0.5,
    ) as browser:
        page = browser.pages[-1] if browser.pages else await browser.new_page()
        await startup_epic_awesome_gamer(page)


if __name__ == "__main__":
    asyncio.run(main())
