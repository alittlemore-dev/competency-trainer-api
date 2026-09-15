from dishka import Provider, Scope, provide

from core.articles.storages import ArticlesStorage
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.wiki_links.use_cases import WikiLinksUseCase


class WikiLinksProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def provide_wiki_links_use_case(
        self,
        articles_storage: ArticlesStorage,
        matrix_storage: CompetencyMatrixStorage,
    ) -> WikiLinksUseCase:
        return WikiLinksUseCase(
            articles_storage=articles_storage,
            matrix_storage=matrix_storage,
        )
