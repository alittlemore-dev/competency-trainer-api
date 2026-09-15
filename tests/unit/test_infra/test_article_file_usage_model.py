from core.files.enums import FilePurpose
from infra.postgresql.models.articles import ArticleFileUsageModel
from tests.test_cases import TestCase


class TestArticleFileUsageModel(TestCase):
    def test_builds_usage_links_from_article_domain_schema(self) -> None:
        first_file_id = self.factory.core.hex_id(31)
        second_file_id = self.factory.core.hex_id(30)
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(10),
            content_file_ids=frozenset({first_file_id, second_file_id}),
        )

        links = ArticleFileUsageModel.from_domain_schema(article=article)

        assert [(link.article_id, link.file_id, link.usage) for link in links] == [
            (article.id, second_file_id, FilePurpose.ARTICLE_CONTENT_IMAGE),
            (article.id, first_file_id, FilePurpose.ARTICLE_CONTENT_IMAGE),
        ]
