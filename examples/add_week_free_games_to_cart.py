import asyncio

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page

from epic_awesome_gamer import EpicSettings
from epic_awesome_gamer.collector import EpicAgent


async def startup_epic_awesome_gamer(page: Page):
    epic_settings = EpicSettings()
    agent = EpicAgent(page, epic_settings)

    urls = [
        "https://store.epicgames.com/en-US/p/bloompunk-2fd3fd",
        "https://store.epicgames.com/en-US/p/fall-guys",
        "https://store.epicgames.com/en-US/p/lords-of-the-fallen-2-lords-of-the-fallen-free-coop-mode-81b41f",
        "https://store.epicgames.com/en-US/p/once-upon-a-puppet-08ad66",
    ]
    await agent.epic_games.add_promotion_to_cart(page, urls=urls)
    await page.goto("https://store.epicgames.com/en-US/cart", wait_until="networkidle")
    await page.wait_for_timeout(5000)


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
