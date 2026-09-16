import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from dishka import AsyncContainer, make_async_container
from dishka.integrations.litestar import LitestarProvider, setup_dishka
from litestar import Litestar
from litestar.middleware import DefineMiddleware
from litestar.testing import TestClient

from core.identity import RoleEnum, UserIdentity
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.config.settings import Settings
from infra.ioc.prodivers.database_provider import DatabaseProvider
from tests.helpers.identity import (
    TestIdentityController,
    TestIdentityMiddleware,
    TestIdentityProvider,
)
from tests.unit.mocks.providers.agent_access import MockAgentAccessProvider
from tests.unit.mocks.providers.articles import MockArticlesProvider
from tests.unit.mocks.providers.cache_tools import MockCacheToolsProvider
from tests.unit.mocks.providers.competency_matrix import MockCompetencyMatrixProvider
from tests.unit.mocks.providers.contacts import MockContactsProvider
from tests.unit.mocks.providers.files import MockFilesProvider
from tests.unit.mocks.providers.general import MockGeneralProvider
from tests.unit.mocks.providers.healthcheck import MockHealthcheckProvider
from tests.unit.mocks.providers.wiki_links import MockWikiLinksProvider


@pytest.fixture
def random_suffix(global_random_uuid: uuid.UUID) -> str:
    return global_random_uuid.hex[:8]


@pytest.fixture
def user_identity() -> UserIdentity:
    return UserIdentity(username="test", role=RoleEnum.USER)


@pytest.fixture
def admin_identity() -> UserIdentity:
    return UserIdentity(username="test", role=RoleEnum.ADMIN)


@pytest.fixture
def identity_controller(admin_identity: UserIdentity) -> TestIdentityController:
    return TestIdentityController(user=admin_identity)


@pytest_asyncio.fixture(loop_scope="function")
async def container(
    test_settings: Settings,
    identity_controller: TestIdentityController,
    global_random_uuid: uuid.UUID,
    global_random_hex_uuid: str,
    random_suffix: str,
) -> AsyncGenerator[AsyncContainer]:
    container = make_async_container(
        LitestarProvider(),
        DatabaseProvider(),
        MockGeneralProvider(uuid_=global_random_uuid, hex_uuid=global_random_hex_uuid),
        MockFilesProvider(random_suffix=random_suffix),
        MockCompetencyMatrixProvider(),
        MockArticlesProvider(),
        MockContactsProvider(),
        MockAgentAccessProvider(),
        TestIdentityProvider(controller=identity_controller),
        MockCacheToolsProvider(),
        MockWikiLinksProvider(),
        MockHealthcheckProvider(),
    )
    yield container
    await container.close()


@pytest.fixture
def app(container: AsyncContainer, identity_controller: TestIdentityController) -> Litestar:
    return build_test_app(container=container, identity_controller=identity_controller)


@pytest.fixture
def no_auth_app(container: AsyncContainer) -> Litestar:
    return build_test_app(
        container=container,
        identity_controller=TestIdentityController(user=UserIdentity.anonymous()),
    )


def build_test_app(
    container: AsyncContainer,
    identity_controller: TestIdentityController,
) -> Litestar:
    test_app = create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[
            DefineMiddleware(TestIdentityMiddleware, controller=identity_controller),
        ],
    )
    setup_dishka(container=container, app=test_app)
    return test_app


@pytest.fixture
def no_auth_client(no_auth_app: Litestar) -> Generator[TestClient]:
    with TestClient(no_auth_app) as client:
        yield client


@pytest.fixture
def client(app: Litestar) -> Generator[TestClient]:
    with TestClient(app) as client:
        yield client
