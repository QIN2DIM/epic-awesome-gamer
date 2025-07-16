import asyncio

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page

from services.epic_agent_service import EpicAgent
from settings import EpicSettings, USER_DATA_DIR


async def startup_epic_awesome_gamer(page: Page):
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)
    await agent.collect_epic_games()


async def invoke():
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1000, min_width=1440),
        humanize=0.2,
    ) as browser:
        page = browser.pages[-1] if browser.pages else await browser.new_page()
        await startup_epic_awesome_gamer(page)


if __name__ == "__main__":
    asyncio.run(invoke())
