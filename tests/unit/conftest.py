import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from dishka import AsyncContainer, make_async_container
from dishka.integrations.litestar import LitestarProvider, setup_dishka
from litestar import Litestar
from litestar.testing import TestClient

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.auth.types import RawToken
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.config.settings import Settings
from infra.ioc.prodivers.database_provider import DatabaseProvider
from tests.unit.mocks.providers.account import MockUserAccountProvider
from tests.unit.mocks.providers.agent_access import MockAgentAccessProvider
from tests.unit.mocks.providers.articles import MockArticlesProvider
from tests.unit.mocks.providers.auth import MockAuthProvider
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
def jwt_user() -> JwtUser:
    return JwtUser(username="test", role=RoleEnum.USER)


@pytest.fixture
def jwt_admin() -> JwtUser:
    return JwtUser(username="test", role=RoleEnum.ADMIN)


@pytest.fixture
def raw_token() -> RawToken:
    return RawToken("Bearer token")


@pytest_asyncio.fixture(loop_scope="function")
async def container(  # noqa: PLR0913
    test_settings: Settings,
    jwt_admin: JwtUser,
    raw_token: RawToken,
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
        MockUserAccountProvider(),
        MockAgentAccessProvider(),
        MockAuthProvider(settings=test_settings, user=jwt_admin, raw_token=raw_token),
        MockCacheToolsProvider(),
        MockWikiLinksProvider(),
        MockHealthcheckProvider(),
    )
    yield container
    await container.close()


@pytest.fixture
def app(container: AsyncContainer) -> Litestar:
    return build_test_app(container=container)


@pytest.fixture
def no_auth_app(container: AsyncContainer) -> Litestar:
    return build_test_app(container=container)


def build_test_app(container: AsyncContainer) -> Litestar:
    test_app = create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[],
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
        client.headers["Authorization"] = "Bearer ANY"
        yield client
