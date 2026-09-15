from litestar import Router

from entrypoints.litestar.api.account.endpoints import api_router as account_router
from entrypoints.litestar.api.accounts.endpoints import admin_router as accounts_admin_router
from entrypoints.litestar.api.admin_tools.endpoints import admin_router as admin_tools_router
from entrypoints.litestar.api.agent_clients.endpoints import (
    admin_router as agent_clients_admin_router,
)
from entrypoints.litestar.api.articles.endpoints import admin_router as articles_admin_router
from entrypoints.litestar.api.articles.endpoints import api_router as articles_router
from entrypoints.litestar.api.auth.endpoints import api_router as auth_router
from entrypoints.litestar.api.competency_matrix.endpoints import (
    admin_router as competency_matrix_admin_router,
)
from entrypoints.litestar.api.competency_matrix.endpoints import (
    api_router as competency_matrix_router,
)
from entrypoints.litestar.api.contacts.endpoints import api_router as contacts_router
from entrypoints.litestar.api.files.endpoints import admin_router as files_admin_router
from entrypoints.litestar.api.healthcheck.endpoints import api_router as healthcheck_router
from entrypoints.litestar.api.i18n.endpoints import api_router as i18n_router
from entrypoints.litestar.api.wiki_links.endpoints import admin_router as wiki_links_admin_router

admin_api_router = Router(
    "/admin",
    route_handlers=[
        accounts_admin_router,
        admin_tools_router,
        agent_clients_admin_router,
        competency_matrix_admin_router,
        files_admin_router,
        articles_admin_router,
        wiki_links_admin_router,
    ],
    tags=["admin api"],
    include_in_schema=False,
)

api_router = Router(
    "/api",
    route_handlers=[
        healthcheck_router,
        i18n_router,
        competency_matrix_router,
        contacts_router,
        auth_router,
        account_router,
        articles_router,
        admin_api_router,
    ],
    tags=["api"],
)
