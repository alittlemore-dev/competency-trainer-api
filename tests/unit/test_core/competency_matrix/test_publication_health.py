from collections.abc import Mapping
from typing import Any

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.schemas import CompetencyMatrixMissingFieldEnum
from core.enums import PublishStatusEnum
from tests.test_cases import TestCase


class TestCompetencyMatrixPublicationHealth(TestCase):
    @pytest.mark.parametrize(
        ("overrides", "missing_field"),
        [
            ({"slug": "   "}, CompetencyMatrixMissingFieldEnum.SLUG),
            ({"grade": None}, CompetencyMatrixMissingFieldEnum.GRADE),
            ({"question_ru": "   "}, CompetencyMatrixMissingFieldEnum.QUESTION_RU),
            ({"question_en": "   "}, CompetencyMatrixMissingFieldEnum.QUESTION_EN),
            ({"answer_ru": "   "}, CompetencyMatrixMissingFieldEnum.ANSWER_RU),
            ({"answer_en": "   "}, CompetencyMatrixMissingFieldEnum.ANSWER_EN),
            (
                {"interview_answer_explanation_ru": "   "},
                CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_RU,
            ),
            (
                {"interview_answer_explanation_en": "   "},
                CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_EN,
            ),
        ],
    )
    def test_published_item_with_missing_required_field_is_not_public_ready(
        self,
        overrides: Mapping[str, Any],
        missing_field: CompetencyMatrixMissingFieldEnum,
    ) -> None:
        item = self.factory.core.competency_matrix_item(
            **{
                "item_id": 1,
                "publish_status": PublishStatusEnum.PUBLISHED,
                "grade": GradeEnum.JUNIOR,
                **overrides,
            },
        )

        assert item.is_available() is False
        assert missing_field in item.missing_publication_fields()

    def test_resources_are_not_required_for_public_readiness(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=1,
            publish_status=PublishStatusEnum.PUBLISHED,
            grade=GradeEnum.JUNIOR,
            resources=[],
        )

        assert item.is_available() is True
        assert item.missing_publication_fields() == ()

    def test_interview_frequency_is_not_required_for_public_readiness(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=1,
            publish_status=PublishStatusEnum.PUBLISHED,
            grade=GradeEnum.JUNIOR,
            interview_frequency=None,
        )

        assert item.is_available() is True
        assert item.missing_publication_fields() == ()
