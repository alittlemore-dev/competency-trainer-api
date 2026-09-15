import click
from litestar import Litestar
from litestar.plugins import CLIPluginProtocol

from entrypoints.litestar.cli.commands.admin import create_admin_command
from entrypoints.litestar.cli.commands.cache import invalidate_cache_command
from entrypoints.litestar.cli.commands.storage import init_buckets_command
from entrypoints.litestar.cli.utils import run_sync


class CLIPlugin(CLIPluginProtocol):
    def on_cli_init(self, cli: click.Group) -> None:
        @cli.command()
        @click.option("--username", "-U", help="Owner username")
        @click.option("--password", "-P", help="Owner password")
        def createsuperuser(app: Litestar, username: str, password: str) -> None:  # noqa: ARG001
            """Create the admin-panel owner."""

            run_sync(create_admin_command(username, password))

        @cli.command()
        def initbuckets(app: Litestar) -> None:  # noqa: ARG001
            run_sync(init_buckets_command())

        @cli.command()
        def invalidatecache(app: Litestar) -> None:
            run_sync(invalidate_cache_command(app))
