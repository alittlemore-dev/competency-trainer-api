import asyncio
from datetime import UTC, datetime

from infra.config.agent_access import load_agent_bridge_settings
from infra.config.constants import constants
from infra.ioc.agent_bridge import compose_agent_bridge_runtime


def main() -> None:
    settings = load_agent_bridge_settings(env_file=constants.path.env_file)
    runtime = compose_agent_bridge_runtime(settings=settings, transport=None)
    if runtime.automatic_rotation is not None:
        asyncio.run(
            runtime.automatic_rotation.use_case.rotate_if_needed(
                current_datetime=datetime.now(UTC),
                policy=runtime.automatic_rotation.policy,
            ),
        )
    runtime.server.server.run(transport="stdio")


if __name__ == "__main__":
    main()
