import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from core.wiki_links.enums import WikiLinkTargetTypeEnum
from core.wiki_links.schemas import WikiLinkTarget, WikiLinkTargetGroup, WikiLinkTargets
from tests.test_cases import ApiTestCase


class TestWikiLinkTargetsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_wiki_links_use_case()

    def test_list_targets(self) -> None:
        self.use_case.list_targets.return_value = WikiLinkTargets(
            values=[
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.ARTICLES,
                    items=[
                        WikiLinkTarget(
                            slug="typed-articles",
                            title="Типизированные статьи",
                            publish_status=PublishStatusEnum.PUBLISHED,
                        ),
                    ],
                ),
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.MATRIX,
                    items=[
                        WikiLinkTarget(
                            slug="how-to-write-function",
                            title="Как написать функцию",
                            publish_status=PublishStatusEnum.DRAFT,
                        ),
                    ],
                ),
            ],
        )

        response = self.api.get_wiki_link_targets(language="ru")

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "targets": [
                {
                    "type": "articles",
                    "items": [
                        {
                            "slug": "typed-articles",
                            "title": "Типизированные статьи",
                            "publishStatus": "Published",
                        },
                    ],
                },
                {
                    "type": "matrix",
                    "items": [
                        {
                            "slug": "how-to-write-function",
                            "title": "Как написать функцию",
                            "publishStatus": "Draft",
                        },
                    ],
                },
            ],
        }
        self.use_case.list_targets.assert_called_once_with(language=LanguageEnum.RU)

    def test_requires_explicit_language(self) -> None:
        response = self.api.get_wiki_link_targets(language=None)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_targets.assert_not_called()

    def test_requires_content_access(self) -> None:
        response = self.no_auth_api.get_wiki_link_targets(language="ru")

        assert response.status_code == codes.UNAUTHORIZED
        self.use_case.list_targets.assert_not_called()

    def test_allows_moderator(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.use_case.list_targets.return_value = WikiLinkTargets(values=[])

        response = self.api.get_wiki_link_targets(language="ru")

        assert response.status_code == codes.OK, response.content
        self.use_case.list_targets.assert_called_once_with(language=LanguageEnum.RU)
