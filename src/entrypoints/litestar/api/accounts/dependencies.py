from core.account.schemas import ManagedAccountFilters
from entrypoints.litestar.api.parameters import PageQuery, PageSizeQuery


def provide_managed_account_filters(
    page: PageQuery,
    page_size: PageSizeQuery,
) -> ManagedAccountFilters:
    return ManagedAccountFilters(page=page, page_size=page_size)
