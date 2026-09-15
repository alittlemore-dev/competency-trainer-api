from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from dishka import AsyncContainer
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.api import APIHelper
from tests.helpers.app import IocContainerHelper
from tests.helpers.assertions import AssertsHelper
from tests.helpers.collections import CollectionsHelper
from tests.helpers.factory import FactoryHelper
from tests.helpers.storage import StorageHelper


class TestCase:
    asserts: AssertsHelper
    collections: CollectionsHelper
    factory: FactoryHelper

    @pytest.fixture(autouse=True)
    def _setup_common_helpers(self) -> None:
        self.asserts = AssertsHelper()
        self.collections = CollectionsHelper()
        self.factory = FactoryHelper()


class StorageTestCase(TestCase):
    db_session: AsyncSession
    storage_helper: StorageHelper

    @pytest_asyncio.fixture(autouse=True)
    async def _setup_storage(self, session: AsyncSession) -> AsyncGenerator[None]:
        self.db_session = session
        self.storage_helper = StorageHelper(session=session)
        yield
        await self.db_session.rollback()


class ContainerTestCase(TestCase):
    container: IocContainerHelper

    @pytest.fixture(autouse=True)
    def _setup_app(
        self,
        container: AsyncContainer,
    ) -> None:
        self.container = IocContainerHelper(container=container)


class ApiTestCase(ContainerTestCase):
    api: APIHelper
    no_auth_api: APIHelper

    @pytest.fixture(autouse=True)
    def _setup_api(
        self,
        client: TestClient,
        no_auth_client: TestClient,
    ) -> None:
        self.api = APIHelper(client=client)
        self.no_auth_api = APIHelper(client=no_auth_client)
