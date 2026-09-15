import uuid
from dataclasses import dataclass
from typing import cast
from unittest.mock import Mock

from dishka import AsyncContainer

from core.account.storages import UserAccountStorage
from core.account.use_cases import AccountsUseCase
from core.agent_access.use_cases import AgentAdminUseCase
from core.articles.schemas import ArticleAnalyticsConfig
from core.articles.use_cases import ArticleAnalyticsUseCase, ArticlesUseCase
from core.auth.password_hashers import PasswordHasher
from core.auth.storages import AuthSessionStorage, AuthStorage
from core.auth.token_handlers import TokenHandler
from core.auth.use_cases import AuthSessionCleanupUseCase, AuthUseCase
from core.cache_tools.schemas import CacheToolsPolicy
from core.cache_tools.use_cases import CacheToolsUseCase
from core.competency_matrix.generators import ItemIdGenerator, ResourceIdGenerator
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.contacts.use_cases import ContactsUseCase
from core.files.file_name_generators import FileNameGenerator
from core.files.services import FileService
from core.generators import HexUuidIdGenerator
from core.types import IntId
from core.wiki_links.use_cases import WikiLinksUseCase
from infra.healthcheck import ReadinessChecker


@dataclass(kw_only=True)
class IocContainerHelper:
    container: AsyncContainer

    # COMMON
    async def get_random_uuid(self) -> uuid.UUID:
        return await self.container.get(uuid.UUID)

    async def get_random_int(self) -> IntId:
        return await self.container.get(IntId)

    async def get_hex_uuid_id_generator(self) -> HexUuidIdGenerator:
        return await self.container.get(HexUuidIdGenerator)

    async def get_item_id_generator(self) -> ItemIdGenerator:
        return await self.container.get(ItemIdGenerator)

    async def get_resource_id_generator(self) -> ResourceIdGenerator:
        return await self.container.get(ResourceIdGenerator)

    # CONTACTS
    async def get_contacts_use_case(self) -> Mock:
        use_case = await self.container.get(ContactsUseCase)
        return cast("Mock", use_case)

    # COMPETENCY MATRIX
    async def get_competency_matrix_use_case(self) -> Mock:
        use_case = await self.container.get(CompetencyMatrixUseCase)
        return cast("Mock", use_case)

    # ARTICLES
    async def get_articles_use_case(self) -> Mock:
        use_case = await self.container.get(ArticlesUseCase)
        return cast("Mock", use_case)

    async def get_article_analytics_use_case(self) -> Mock:
        use_case = await self.container.get(ArticleAnalyticsUseCase)
        return cast("Mock", use_case)

    async def get_article_analytics_config(self) -> ArticleAnalyticsConfig:
        return await self.container.get(ArticleAnalyticsConfig)

    async def get_wiki_links_use_case(self) -> Mock:
        use_case = await self.container.get(WikiLinksUseCase)
        return cast("Mock", use_case)

    # AUTH
    async def get_hasher(self) -> Mock:
        hasher = await self.container.get(PasswordHasher)
        return cast("Mock", hasher)

    async def get_token_handler(self) -> Mock:
        handler = await self.container.get(TokenHandler)
        return cast("Mock", handler)

    async def get_auth_storage(self) -> Mock:
        storage = await self.container.get(AuthStorage)
        return cast("Mock", storage)

    async def get_auth_session_storage(self) -> Mock:
        storage = await self.container.get(AuthSessionStorage)
        return cast("Mock", storage)

    async def get_auth_use_case(self) -> Mock:
        use_case = await self.container.get(AuthUseCase)
        return cast("Mock", use_case)

    async def get_auth_session_cleanup_use_case(self) -> Mock:
        use_case = await self.container.get(AuthSessionCleanupUseCase)
        return cast("Mock", use_case)

    async def get_cache_tools_use_case(self) -> Mock:
        use_case = await self.container.get(CacheToolsUseCase)
        return cast("Mock", use_case)

    async def get_cache_tools_policy(self) -> CacheToolsPolicy:
        return await self.container.get(CacheToolsPolicy)

    # USER
    async def get_user_storage(self) -> Mock:
        storage = await self.container.get(UserAccountStorage)
        return cast("Mock", storage)

    async def get_accounts_use_case(self) -> Mock:
        use_case = await self.container.get(AccountsUseCase)
        return cast("Mock", use_case)

    async def get_agent_admin_use_case(self) -> Mock:
        use_case = await self.container.get(AgentAdminUseCase)
        return cast("Mock", use_case)

    # FILES
    async def get_file_name_generator(self) -> Mock:
        generator = await self.container.get(FileNameGenerator)
        return cast("Mock", generator)

    async def get_file_service(self) -> Mock:
        service = await self.container.get(FileService)
        return cast("Mock", service)

    async def get_readiness_checker(self) -> Mock:
        checker = await self.container.get(ReadinessChecker)
        return cast("Mock", checker)
