from dataclasses import dataclass

from core.articles.storages import ArticlesStorage
from core.competency_matrix.schemas import CompetencyMatrixItemFilters
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.i18n.enums import LanguageEnum
from core.wiki_links.enums import WikiLinkTargetTypeEnum
from core.wiki_links.schemas import WikiLinkTarget, WikiLinkTargetGroup, WikiLinkTargets


@dataclass(kw_only=True, slots=True, frozen=True)
class WikiLinksUseCase:
    articles_storage: ArticlesStorage
    matrix_storage: CompetencyMatrixStorage

    async def list_targets(self, *, language: LanguageEnum) -> WikiLinkTargets:
        article_items = await self.articles_storage.list_tree_items(
            only_published=False,
            language=language,
        )
        matrix_items = await self.matrix_storage.list_competency_matrix_items(
            filters=CompetencyMatrixItemFilters(only_published=False),
        )
        return WikiLinkTargets(
            values=[
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.ARTICLES,
                    items=[
                        WikiLinkTarget(
                            slug=article.slug,
                            title=article.title,
                            publish_status=article.publish_status,
                        )
                        for article in article_items
                    ],
                ),
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.MATRIX,
                    items=[
                        WikiLinkTarget(
                            slug=item.slug,
                            title=item.localized_question(language=language),
                            publish_status=item.publish_status,
                        )
                        for item in matrix_items
                    ],
                ),
            ],
        )
