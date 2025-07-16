import asyncio
from typing import List

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page

from services.epic_agent_service import EpicAgent
from settings import EpicSettings, USER_DATA_DIR


async def startup_epic_awesome_gamer(page: Page, urls: List[str] | None = None):
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)

    urls = urls or [
        "https://store.epicgames.com/en-US/p/bloompunk-2fd3fd",
        "https://store.epicgames.com/en-US/p/fall-guys",
        "https://store.epicgames.com/en-US/p/lords-of-the-fallen-2-lords-of-the-fallen-free-coop-mode-81b41f",
        "https://store.epicgames.com/en-US/p/once-upon-a-puppet-08ad66",
    ]
    await agent.epic_games.add_promotion_to_cart(page, urls=urls)
    await page.goto("https://store.epicgames.com/en-US/cart", wait_until="networkidle")
    await page.wait_for_timeout(5000)


async def invoke(urls: List[str] | None = None):
    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=USER_DATA_DIR,
        screen=Screen(max_width=1920, max_height=1080, min_height=1000, min_width=1440),
        humanize=0.2,
    ) as browser:
        page = await browser.new_page()
        await startup_epic_awesome_gamer(page, urls)


if __name__ == "__main__":
    asyncio.run(invoke())
