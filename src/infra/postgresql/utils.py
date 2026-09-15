from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config

from infra.config.constants import constants


def migrate(revision: str) -> None:
    config = Config(constants.path.alembic_dir / "alembic.ini")
    alembic_upgrade(config=config, revision=revision)


def downgrade(revision: str) -> None:
    config = Config(constants.path.alembic_dir / "alembic.ini")
    alembic_downgrade(config=config, revision=revision)
