from pathlib import Path

from hcaptcha_challenger.agent import AgentConfig

from epic_awesome_gamer import EpicSettings
from epic_awesome_gamer.helper.env_generator import generate_env_example_merged


def test_env_generator():
    current_dir = Path(__file__).parent
    output_dir = Path(__file__).parent

    launch_names = ["examples", "docker", "tests"]
    for name in launch_names:
        if current_dir.joinpath(name).is_dir():
            output_dir = current_dir.joinpath(name)
        elif current_dir.parent.joinpath(name).is_dir():
            output_dir = current_dir.parent.joinpath(name)

        generate_env_example_merged([EpicSettings, AgentConfig], output_dir=output_dir)
