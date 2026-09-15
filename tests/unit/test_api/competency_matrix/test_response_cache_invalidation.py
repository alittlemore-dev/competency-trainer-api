import pytest
import pytest_asyncio
from httpx import codes

from core.competency_matrix.exceptions import CompetencyMatrixStructurePriorityInvalidError
from core.enums import PublishStatusEnum
from entrypoints.litestar.response_cache import ResponseCacheDomain
from tests.test_cases import ApiTestCase


class TestCompetencyMatrixResponseCacheInvalidation(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_successful_matrix_mutations_schedule_matrix_cache_invalidation(
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
            "entrypoints.litestar.api.competency_matrix.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )
        self.use_case.create_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            publish_status=PublishStatusEnum.DRAFT,
        )
        self.use_case.update_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        self.use_case.create_item_from_queue.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=2,
                publish_status=PublishStatusEnum.DRAFT,
            )
        )

        responses = [
            self.api.post_create_item(data=self.factory.api.competency_matrix_item_request()),
            self.api.post_create_item_from_queue(
                question_id=1,
                data=self.factory.api.competency_matrix_item_request(slug="queued-question"),
            ),
            self.api.put_update_item(pk=1, data=self.factory.api.competency_matrix_item_request()),
            self.api.delete_item(pk=1),
            self.api.post_set_published_status_to_item(pk=1),
            self.api.post_set_draft_status_to_item(pk=1),
            self.api.put_update_matrix_sheet_priorities(ordered_ids=[2, 1]),
            self.api.put_update_matrix_section_priorities(sheet_id=1, ordered_ids=[2, 1]),
            self.api.put_update_matrix_subsection_priorities(section_id=1, ordered_ids=[2, 1]),
        ]

        assert [response.status_code for response in responses] == [
            codes.CREATED,
            codes.CREATED,
            codes.OK,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
        ]
        assert invalidated_domains == [ResponseCacheDomain.COMPETENCY_MATRIX] * 9

    def test_item_validation_error_does_not_schedule_matrix_cache_invalidation(
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
            "entrypoints.litestar.api.competency_matrix.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )

        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(),
            language=None,
        )

        assert response.status_code == codes.BAD_REQUEST
        assert invalidated_domains == []

    def test_structure_priority_error_does_not_schedule_matrix_cache_invalidation(
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
            "entrypoints.litestar.api.competency_matrix.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )
        self.use_case.update_sheet_priorities.side_effect = (
            CompetencyMatrixStructurePriorityInvalidError
        )

        response = self.api.put_update_matrix_sheet_priorities(ordered_ids=[2, 1])

        assert response.status_code == codes.BAD_REQUEST
        assert invalidated_domains == []
