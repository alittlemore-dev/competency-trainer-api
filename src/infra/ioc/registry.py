from collections.abc import Iterable

from dishka import Provider
from dishka.integrations.litestar import LitestarProvider

from infra.config.settings import settings
from infra.ioc.prodivers.agent_access_provider import AgentAccessProvider
from infra.ioc.prodivers.agent_admin_provider import AgentAdminProvider
from infra.ioc.prodivers.articles_provider import ArticlesProvider
from infra.ioc.prodivers.competency_matrix_provider import CompetencyMatrixProvider
from infra.ioc.prodivers.contacts_provider import ContactsProvider
from infra.ioc.prodivers.database_provider import DatabaseProvider
from infra.ioc.prodivers.files_provider import FilesProvider
from infra.ioc.prodivers.general_provider import GeneralProvider
from infra.ioc.prodivers.healthcheck_provider import HealthcheckProvider
from infra.ioc.prodivers.response_cache_warm_provider import ResponseCacheWarmProvider
from infra.ioc.prodivers.wiki_links_provider import WikiLinksProvider


def get_providers() -> Iterable[Provider]:
    return (
        GeneralProvider(),
        FilesProvider(),
        DatabaseProvider(),
        AgentAdminProvider(
            settings=settings.agent_access,
        ),
        AgentAccessProvider(),
        LitestarProvider(),
        CompetencyMatrixProvider(),
        ContactsProvider(),
        ArticlesProvider(),
        WikiLinksProvider(),
        ResponseCacheWarmProvider(),
        HealthcheckProvider(),
    )
