from collections.abc import Generator

import pytest

from infra.postgresql.utils import downgrade, migrate
from tests.helpers.assertions import AssertsHelper


@pytest.fixture
def migrated_to_0001() -> Generator[None]:
    migrate(revision="0001")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0002() -> Generator[None]:
    migrate(revision="0002")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0004() -> Generator[None]:
    migrate(revision="0004")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0005() -> Generator[None]:
    migrate(revision="0005")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0006() -> Generator[None]:
    migrate(revision="0006")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0007() -> Generator[None]:
    migrate(revision="0007")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0008() -> Generator[None]:
    migrate(revision="0008")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0009() -> Generator[None]:
    migrate(revision="0009")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0010() -> Generator[None]:
    migrate(revision="0010")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0011() -> Generator[None]:
    migrate(revision="0011")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0012() -> Generator[None]:
    migrate(revision="0012")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0013() -> Generator[None]:
    migrate(revision="0013")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0014() -> Generator[None]:
    migrate(revision="0014")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0015() -> Generator[None]:
    migrate(revision="0015")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0016() -> Generator[None]:
    migrate(revision="0016")
    yield
    downgrade(revision="base")


@pytest.fixture
def migrated_to_0017() -> Generator[None]:
    migrate(revision="0017")
    yield
    downgrade(revision="base")


@pytest.fixture
def migration_asserts() -> AssertsHelper:
    return AssertsHelper()
