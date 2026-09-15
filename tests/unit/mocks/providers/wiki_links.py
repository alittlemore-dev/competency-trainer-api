from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.wiki_links.use_cases import WikiLinksUseCase


class MockWikiLinksProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_wiki_links_use_case(self) -> WikiLinksUseCase:
        return Mock(spec=WikiLinksUseCase)
