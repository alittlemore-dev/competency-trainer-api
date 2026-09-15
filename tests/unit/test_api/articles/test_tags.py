import pytest
import pytest_asyncio
from httpx import codes

from core.articles.schemas import TagCreateParams, TagUpdateParams
from core.auth.exceptions import UnauthorizedError
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.response_cache import ResponseCacheDomain
from tests.test_cases import ApiTestCase


class TestTagsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.tag_id = (await self.container.get_hex_uuid_id_generator()).get_next()
        self.use_case = await self.container.get_articles_use_case()

    def test_list_tags(self) -> None:
        self.use_case.list_tags.return_value = self.factory.core.tags(
            values=[
                self.factory.core.tag(
                    tag_id="00000000000040008000000000000101",
                    name="Python",
                    slug="python",
                ),
                self.factory.core.tag(
                    tag_id="00000000000040008000000000000102",
                    name="Django",
                    slug="django",
                ),
            ],
        )

        response = self.api.get_admin_tags()

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "tags": [
                {
                    "id": "00000000000040008000000000000101",
                    "name": "Python",
                    "slug": "python",
                    "translations": {
                        "ru": {"name": "Python"},
                        "en": {"name": "Python"},
                    },
                },
                {
                    "id": "00000000000040008000000000000102",
                    "name": "Django",
                    "slug": "django",
                    "translations": {
                        "ru": {"name": "Django"},
                        "en": {"name": "Django"},
                    },
                },
            ],
        }
        self.use_case.list_tags.assert_called_once_with(
            language=LanguageEnum.RU,
            only_with_published_articles=False,
        )

    def test_list_tags_requires_explicit_language(self) -> None:
        response = self.api.get_tags(language=None)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_tags.assert_not_called()

    def test_public_list_tags(self) -> None:
        self.use_case.list_tags.return_value = self.factory.core.tags(values=[])

        response = self.no_auth_api.get_tags()

        assert response.status_code == codes.OK, response.content
        self.use_case.list_tags.assert_called_once_with(
            language=LanguageEnum.RU,
            only_with_published_articles=True,
        )

    def test_anonymous_cannot_list_admin_tags(self) -> None:
        response = self.no_auth_api.get_admin_tags()

        assert response.status_code == codes.UNAUTHORIZED
        assert response.json()["message"] == UnauthorizedError.message
        self.use_case.list_tags.assert_not_called()

    def test_search_tags(self) -> None:
        self.use_case.search_tags.return_value = self.factory.core.tags(
            values=[
                self.factory.core.tag(
                    tag_id="00000000000040008000000000000101",
                    name="Python",
                    slug="python",
                ),
            ],
        )

        response = self.api.get_search_tags(search_name="py", limit=5)

        assert response.status_code == codes.OK, response.content
        self.use_case.search_tags.assert_called_once_with(
            search_name="py",
            limit=5,
            language=LanguageEnum.RU,
        )

    def test_create_tag(self) -> None:
        tag = self.factory.core.tag(
            tag_id=self.tag_id,
            name="Бэкенд",
            name_ru="Бэкенд",
            name_en="Backend",
            slug="backend",
        )
        self.use_case.create_tag.return_value = tag

        response = self.api.post_create_tag(
            data=self.factory.api.tag_request(name_ru="Бэкенд", name_en="Backend", slug="backend"),
        )

        assert response.status_code == codes.CREATED, response.content
        assert response.json() == {
            "id": self.tag_id,
            "name": "Бэкенд",
            "slug": "backend",
            "translations": {
                "ru": {"name": "Бэкенд"},
                "en": {"name": "Backend"},
            },
        }
        self.use_case.create_tag.assert_called_once_with(
            params=TagCreateParams(
                id=self.tag_id,
                name_ru="Бэкенд",
                name_en="Backend",
                slug="backend",
            ),
        )

    def test_update_tag(self) -> None:
        self.use_case.update_tag.return_value = self.factory.core.tag(
            tag_id="00000000000040008000000000000003",
            name="Архитектура",
            name_ru="Архитектура",
            name_en="Architecture",
            slug="architecture",
        )

        response = self.api.put_update_tag(
            tag_id="00000000000040008000000000000003",
            data=self.factory.api.tag_request(
                name_ru="Архитектура",
                name_en="Architecture",
                slug="architecture",
            ),
        )

        assert response.status_code == codes.OK, response.content
        self.use_case.update_tag.assert_called_once_with(
            tag_id="00000000000040008000000000000003",
            params=TagUpdateParams(
                name_ru="Архитектура",
                name_en="Architecture",
                slug="architecture",
            ),
        )

    def test_create_tag_requires_all_translation_fields(self) -> None:
        data = self.factory.api.tag_request()
        del data["translations"]["en"]["name"]

        response = self.api.post_create_tag(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_tag.assert_not_called()

    @pytest.mark.parametrize("slug", ["", "   ", "Backend", "backend_tag", "backend--tag"])
    def test_create_tag_rejects_blank_or_invalid_slug(self, slug: str) -> None:
        response = self.api.post_create_tag(data=self.factory.api.tag_request(slug=slug))

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_tag.assert_not_called()

    def test_create_tag_rejects_whitespace_translation_name(self) -> None:
        response = self.api.post_create_tag(
            data=self.factory.api.tag_request(name_ru="   "),
        )

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_tag.assert_not_called()

    def test_delete_tag(self) -> None:
        response = self.api.delete_tag(tag_id="00000000000040008000000000000003")

        assert response.status_code == codes.NO_CONTENT
        self.use_case.delete_tag.assert_called_once_with(
            tag_id="00000000000040008000000000000003",
        )

    def test_restore_tag_endpoint_does_not_exist(self) -> None:
        response = self.api.client.post(
            "/api/admin/articles/tags/00000000000040008000000000000003/restore",
        )

        assert response.status_code == codes.NOT_FOUND

    def test_successful_tag_mutations_schedule_articles_cache_invalidation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        invalidated_domains: list[ResponseCacheDomain] = []

        async def fake_invalidate_response_cache_domain_for_mutation(
            *,
            request: object,
            domain: ResponseCacheDomain,
            post_commit_actions: object,
        ) -> None:
            _ = request, post_commit_actions
            invalidated_domains.append(domain)

        monkeypatch.setattr(
            "entrypoints.litestar.api.articles.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )
        self.use_case.create_tag.return_value = self.factory.core.tag(tag_id=self.tag_id)
        self.use_case.update_tag.return_value = self.factory.core.tag(
            tag_id="00000000000040008000000000000003",
        )

        responses = [
            self.api.post_create_tag(data=self.factory.api.tag_request(slug="backend")),
            self.api.put_update_tag(
                tag_id="00000000000040008000000000000003",
                data=self.factory.api.tag_request(slug="architecture"),
            ),
            self.api.delete_tag(tag_id="00000000000040008000000000000003"),
        ]

        assert [response.status_code for response in responses] == [
            codes.CREATED,
            codes.OK,
            codes.NO_CONTENT,
        ]
        assert invalidated_domains == [ResponseCacheDomain.ARTICLES] * 3
