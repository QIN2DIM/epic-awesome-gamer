import os
import sys
import asyncio
from pathlib import Path

import typer
from typing import Optional

from pydantic import SecretStr
from hcaptcha_challenger.models import SCoTModelType

# Create top-level application
app = typer.Typer(
    name="epic-awesome-gamer",
    help="Epic Games Collector tool",
    add_completion=False,
    invoke_without_command=True,  # Enable callback when no command is passed
)


@app.callback()
def main_callback(ctx: typer.Context):
    """
    Main callback. Shows help if no command is provided.
    """
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


@app.command(name="help", help="Show help for a specific command.")
def help_command(
    ctx: typer.Context,
    command_path: list[str] = typer.Argument(
        None, help="The command path (e.g., 'dataset collect')."
    ),
):
    """
    Provides help for commands, similar to `command --help`.

    Example: hc help dataset collect
    """
    if not command_path:
        # If `hc help` is called with no arguments, show main help
        print(ctx.parent.get_help())
        raise typer.Exit()

    # Get the full command context to search through
    current_ctx = ctx.parent

    # Navigate through the command path to find the target command
    for i, cmd in enumerate(command_path):
        found = False

        # Try to find command in current context
        if hasattr(current_ctx.command, "commands"):
            for name, command in current_ctx.command.commands.items():
                if name == cmd:
                    # Create a new context for this command
                    current_ctx = typer.Context(command, parent=current_ctx, info_name=cmd)
                    found = True
                    break

        if not found:
            # If we didn't find it as a command, it might be a typer app
            # Use --help mechanism directly
            try:
                remaining_path = command_path[i:]
                print(f"Showing help for: {' '.join(remaining_path)}")
                cmd_list = [*sys.argv[0:1], *remaining_path, "--help"]
                app(cmd_list)
                return
            except SystemExit:
                # Typer will exit after showing help
                return
            except Exception:
                print(f"Error: Command '{cmd}' not found")
                raise typer.Exit(code=1)

    # Print help for the found command
    print(current_ctx.get_help())
    raise typer.Exit()


@app.command(name="collect", help="Collect free epic games.")
def collect(
    epic_email: Optional[str] = typer.Option(
        None, "--email", envvar="EPIC_EMAIL", help="Epic Games account email"
    ),
    epic_password: Optional[str] = typer.Option(
        None, "--password", envvar="EPIC_PASSWORD", help="Epic Games account password"
    ),
    gemini_api_key: Optional[str] = typer.Option(
        None, "--gemini-api-key", envvar="GEMINI_API_KEY", help="Gemini API key"
    ),
    user_data_dir: Optional[Path] = typer.Option(
        Path("tmp/.cache/user_data"), "--user-data-dir", help="Directory to store browser user data"
    ),
    all_games: bool = typer.Option(
        False, "--all-games", help="Collect all free games, but may miss weekly free games"
    ),
):
    """
    Collect free games from Epic Games Store.
    """
    from browserforge.fingerprints import Screen
    from camoufox.async_api import AsyncCamoufox
    from playwright.async_api import Page
    from hcaptcha_challenger.agent import AgentConfig

    from epic_awesome_gamer import EpicSettings
    from epic_awesome_gamer.collector import EpicAgent

    if all_games:
        typer.echo("🙌 Not implemented yet.")
        return

    async def startup_epic_awesome_gamer(page: Page):
        epic_settings = EpicSettings()
        solver_config = AgentConfig(DISABLE_BEZIER_TRAJECTORY=True)

        # 如果提供了命令行参数，覆盖环境变量设置
        if epic_email:
            epic_settings.EPIC_EMAIL = epic_email
        if epic_password:
            epic_settings.EPIC_PASSWORD = SecretStr(epic_password)
        if gemini_api_key:
            solver_config.GEMINI_API_KEY = SecretStr(gemini_api_key)

        agent = EpicAgent(page, epic_settings, solver_config)
        await agent.collect_epic_games()

    async def run_collector():
        async with AsyncCamoufox(
            persistent_context=True,
            user_data_dir=str(user_data_dir.resolve()),
            screen=Screen(max_width=1920, max_height=1080),
            humanize=0.5,
        ) as browser:
            page = browser.pages[-1] if browser.pages else await browser.new_page()
            await startup_epic_awesome_gamer(page)

    asyncio.run(run_collector())


def main():
    app()


if __name__ == "__main__":
    main()
