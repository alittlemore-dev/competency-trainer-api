from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.competency_matrix.enums import (
    CompetencyMatrixWorkspaceSortEnum,
    GradeEnum,
    InterviewFrequencyEnum,
)
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemConflictError,
    CompetencyMatrixItemNotFoundError,
    CompetencyMatrixStructureAlreadyExistsError,
    CompetencyMatrixStructureNotFoundError,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixItemFilters,
    CompetencyMatrixMissingFieldEnum,
    CompetencyMatrixSectionCreateParams,
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetCreateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixSubsectionCreateParams,
    CompetencyMatrixSubsectionPriorityUpdateParams,
    CompetencyMatrixWorkspaceFilters,
    CompetencyMatrixWorkspaceSummary,
)
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from tests.test_cases import StorageTestCase


class TestCompetencyMatrixStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.storage = CompetencyMatrixDatabaseStorage(session=session)
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=1,
                    question="1",
                    answer="Answer 1",
                    interview_answer_explanation="Answer explanation 1",
                    sheet="Python",
                    grade=GradeEnum.MIDDLE_PLUS,
                    section="Basics",
                    subsection="Functions",
                    resources=[
                        self.factory.core.attached_external_resource(
                            resource_id=1,
                            name="NAME 1",
                            url="https://example1.com",
                            context="CONTEXT 1",
                        ),
                    ],
                ),
                self.factory.core.competency_matrix_item(
                    item_id=2,
                    sheet_id=2,
                    section_id=2,
                    subsection_id=2,
                    question="2",
                    answer="Answer 2",
                    interview_answer_explanation="Answer explanation 2",
                    sheet="SQL",
                    grade=GradeEnum.SENIOR,
                    section="Basics",
                    subsection="Async",
                    resources=[
                        self.factory.core.attached_external_resource(
                            resource_id=2,
                            name="NAME 2",
                            url="https://example2.com",
                            context="CONTEXT 2",
                        ),
                    ],
                ),
            ],
        )

    async def test_list_sheets(self) -> None:
        sheets = await self.storage.list_sheets()
        assert sheets == self.factory.core.sheets(values=["Python", "SQL"])

    async def test_list_structure_includes_unused_nodes(self) -> None:
        sheet = await self.storage.create_sheet(
            params=CompetencyMatrixSheetCreateParams(
                key="go",
                name_ru="Go",
                name_en="Go",
            ),
        )
        section = await self.storage.create_section(
            params=CompetencyMatrixSectionCreateParams(
                sheet_id=sheet.id,
                name_ru="Concurrency",
                name_en="Concurrency",
            ),
        )
        await self.storage.create_subsection(
            params=CompetencyMatrixSubsectionCreateParams(
                section_id=section.id,
                name_ru="Channels",
                name_en="Channels",
            ),
        )

        structure = await self.storage.list_structure()

        sheets_by_key = {structure_sheet.key: structure_sheet for structure_sheet in structure}
        assert [structure_sheet.key for structure_sheet in structure] == ["python", "sql", "go"]
        assert sheets_by_key["go"].priority == 3
        assert sheets_by_key["go"].sections[0].priority == 1
        assert sheets_by_key["go"].sections[0].subsections[0].priority == 1
        assert sheets_by_key["go"].sections[0].name_en == "Concurrency"
        assert sheets_by_key["go"].sections[0].subsections[0].name_en == "Channels"
        assert sheets_by_key["python"].sections[0].subsections[0].name_en == "Functions"

    async def test_create_structure_nodes_append_priority_to_sibling_end(self) -> None:
        sheet = await self.storage.create_sheet(
            params=CompetencyMatrixSheetCreateParams(
                key="go",
                name_ru="Go",
                name_en="Go",
            ),
        )
        section = await self.storage.create_section(
            params=CompetencyMatrixSectionCreateParams(
                sheet_id=self.factory.core.hex_id(1),
                name_ru="Расширенно",
                name_en="Advanced",
            ),
        )
        subsection = await self.storage.create_subsection(
            params=CompetencyMatrixSubsectionCreateParams(
                section_id=self.factory.core.hex_id(1),
                name_ru="Асинхронность",
                name_en="Async",
            ),
        )

        assert sheet.priority == 3
        assert section.priority == 2
        assert subsection.priority == 2

    async def test_update_structure_priorities_persists_order(self) -> None:
        section = await self.storage.create_section(
            params=CompetencyMatrixSectionCreateParams(
                sheet_id=self.factory.core.hex_id(1),
                name_ru="Расширенно",
                name_en="Advanced",
            ),
        )
        subsection = await self.storage.create_subsection(
            params=CompetencyMatrixSubsectionCreateParams(
                section_id=self.factory.core.hex_id(1),
                name_ru="Асинхронность",
                name_en="Async",
            ),
        )

        await self.storage.update_sheet_priorities(
            params=CompetencyMatrixSheetPriorityUpdateParams(
                ordered_ids=(self.factory.core.hex_id(2), self.factory.core.hex_id(1)),
            ),
        )
        await self.storage.update_section_priorities(
            params=CompetencyMatrixSectionPriorityUpdateParams(
                sheet_id=self.factory.core.hex_id(1),
                ordered_ids=(section.id, self.factory.core.hex_id(1)),
            ),
        )
        await self.storage.update_subsection_priorities(
            params=CompetencyMatrixSubsectionPriorityUpdateParams(
                section_id=self.factory.core.hex_id(1),
                ordered_ids=(subsection.id, self.factory.core.hex_id(1)),
            ),
        )

        sheets = await self.storage.list_sheets()
        structure = await self.storage.list_structure()

        python_sheet = next(sheet for sheet in structure if sheet.key == "python")
        basics_section = next(
            section
            for section in python_sheet.sections
            if section.id == self.factory.core.hex_id(1)
        )
        assert sheets == self.factory.core.sheets(values=["SQL", "Python"])
        assert [sheet.key for sheet in structure] == ["sql", "python"]
        assert [section.name_en for section in python_sheet.sections] == ["Advanced", "Basics"]
        assert [subsection.name_en for subsection in basics_section.subsections] == [
            "Async",
            "Functions",
        ]

    async def test_list_items_uses_structure_priority_order(self) -> None:
        section = await self.storage.create_section(
            params=CompetencyMatrixSectionCreateParams(
                sheet_id=self.factory.core.hex_id(1),
                name_ru="Расширенно",
                name_en="Advanced",
            ),
        )
        subsection = await self.storage.create_subsection(
            params=CompetencyMatrixSubsectionCreateParams(
                section_id=section.id,
                name_ru="Асинхронность",
                name_en="Async",
            ),
        )
        await self.storage.create_competency_matrix_item(
            item=self.factory.core.competency_matrix_item(
                item_id=3,
                sheet="Python",
                section_id=section.id,
                section="Advanced",
                subsection_id=subsection.id,
                subsection="Async",
                question="Advanced question",
                grade=GradeEnum.JUNIOR,
            ),
        )
        await self.storage.update_section_priorities(
            params=CompetencyMatrixSectionPriorityUpdateParams(
                sheet_id=self.factory.core.hex_id(1),
                ordered_ids=(section.id, self.factory.core.hex_id(1)),
            ),
        )

        items = await self.storage.list_competency_matrix_items(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=None),
        )

        assert self.collections.slugs(items) == ["advanced-question", "1"]

    async def test_get_item_structure_by_subsection_id(self) -> None:
        structure = await self.storage.get_item_structure_by_subsection_id(
            subsection_id=self.factory.core.hex_id(1),
        )

        assert structure.sheet_key == "python"
        assert structure.sheet_en == "Python"
        assert structure.section_en == "Basics"
        assert structure.subsection_en == "Functions"

    async def test_get_item_structure_by_subsection_id_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            await self.storage.get_item_structure_by_subsection_id(
                subsection_id=self.factory.core.hex_id(-1),
            )

    async def test_create_structure_rejects_duplicates_and_missing_parents(self) -> None:
        with pytest.raises(CompetencyMatrixStructureAlreadyExistsError):
            await self.storage.create_sheet(
                params=CompetencyMatrixSheetCreateParams(
                    key="PYTHON",
                    name_ru="Python duplicate",
                    name_en="Python duplicate",
                ),
            )
        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            await self.storage.create_section(
                params=CompetencyMatrixSectionCreateParams(
                    sheet_id=self.factory.core.hex_id(-1),
                    name_ru="Missing",
                    name_en="Missing",
                ),
            )
        with pytest.raises(CompetencyMatrixStructureAlreadyExistsError):
            await self.storage.create_section(
                params=CompetencyMatrixSectionCreateParams(
                    sheet_id=self.factory.core.hex_id(1),
                    name_ru="Basics duplicate",
                    name_en="Basics",
                ),
            )
        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            await self.storage.create_subsection(
                params=CompetencyMatrixSubsectionCreateParams(
                    section_id=self.factory.core.hex_id(-1),
                    name_ru="Missing",
                    name_en="Missing",
                ),
            )
        with pytest.raises(CompetencyMatrixStructureAlreadyExistsError):
            await self.storage.create_subsection(
                params=CompetencyMatrixSubsectionCreateParams(
                    section_id=self.factory.core.hex_id(1),
                    name_ru="Functions duplicate",
                    name_en="Functions",
                ),
            )

    async def test_list_items(self) -> None:
        items = await self.storage.list_competency_matrix_items(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=None),
        )
        assert items == [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                answer="Answer 1",
                interview_answer_explanation="Answer explanation 1",
                sheet="Python",
                grade=GradeEnum.MIDDLE_PLUS,
                section="Basics",
                subsection="Functions",
                resources=[],
            ),
        ]

    async def test_get_competency_matrix_item_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(-1))

    async def test_get_competency_matrix_item_found(self) -> None:
        item = await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(1))
        assert item == self.factory.core.competency_matrix_item(
            item_id=1,
            question="1",
            answer="Answer 1",
            interview_answer_explanation="Answer explanation 1",
            sheet="Python",
            grade=GradeEnum.MIDDLE_PLUS,
            section="Basics",
            subsection="Functions",
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=1,
                    name="NAME 1",
                    url="https://example1.com",
                    context="CONTEXT 1",
                ),
            ],
        )

    async def test_get_competency_matrix_item_by_slug_found(self) -> None:
        item = await self.storage.get_competency_matrix_item_by_slug(slug="1")
        assert item == self.factory.core.competency_matrix_item(
            item_id=1,
            question="1",
            answer="Answer 1",
            interview_answer_explanation="Answer explanation 1",
            sheet="Python",
            grade=GradeEnum.MIDDLE_PLUS,
            section="Basics",
            subsection="Functions",
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=1,
                    name="NAME 1",
                    url="https://example1.com",
                    context="CONTEXT 1",
                ),
            ],
        )

    async def test_get_competency_matrix_item_by_slug_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.get_competency_matrix_item_by_slug(slug="missing-question")

    async def test_list_items_filters_by_publish_status_without_availability_check(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    question="Draft question",
                    publish_status=PublishStatusEnum.DRAFT,
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                ),
                self.factory.core.competency_matrix_item(
                    item_id=4,
                    question="Unavailable question",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    answer_en="",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                ),
            ],
        )

        items = await self.storage.list_competency_matrix_items(
            filters=CompetencyMatrixItemFilters(sheet_key=None, only_published=True),
        )

        item_slugs = set(self.collections.slugs(items))
        assert item_slugs == {"1", "2", "unavailable-question"}
        assert "draft-question" not in item_slugs

    async def test_list_workspace_items_filters_sorts_summarizes_and_paginates(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="missing-draft-python",
                    question="Draft Python",
                    publish_status=PublishStatusEnum.DRAFT,
                    answer_en="",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                ),
                self.factory.core.competency_matrix_item(
                    item_id=4,
                    slug="dangerous-published-python",
                    published_at="2024-02-10T00:00:00",
                    question="Dangerous Python",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    answer_en="",
                    subsection_id=3,
                    sheet="Python",
                    grade=GradeEnum.SENIOR,
                    section="Basics",
                    subsection="Async",
                ),
                self.factory.core.competency_matrix_item(
                    item_id=5,
                    slug="ready-published-python",
                    published_at="2024-03-01T00:00:00",
                    question="Ready Python",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    subsection_id=3,
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Async",
                ),
                self.factory.core.competency_matrix_item(
                    item_id=6,
                    slug="ready-published-sql",
                    published_at="2024-04-01T00:00:00",
                    question="Ready SQL",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    sheet_id=2,
                    section_id=2,
                    subsection_id=2,
                    sheet="SQL",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Async",
                ),
            ],
        )

        items, total_count, summary = await self.storage.list_competency_matrix_workspace_items(
            filters=CompetencyMatrixWorkspaceFilters(
                page=1,
                page_size=2,
                language=LanguageEnum.EN,
                sort=CompetencyMatrixWorkspaceSortEnum.DANGEROUS_PUBLISHED,
                search_query="Python",
                sheet_keys=("python",),
                grades=(),
                sections=("Basics",),
                subsections=(),
                publish_statuses=(),
                published_from=None,
                published_to=None,
                has_missing_fields=None,
            ),
        )

        assert total_count == 3
        assert summary == CompetencyMatrixWorkspaceSummary(
            total=3,
            draft=1,
            missing_draft=1,
            dangerous_published=1,
            ready_published=1,
        )
        assert self.collections.slugs(items) == [
            "dangerous-published-python",
            "ready-published-python",
        ]
        assert items[0].question == "Dangerous Python"
        assert items[0].sheet == "Python"
        assert items[0].section == "Basics"
        assert items[0].subsection == "Async"
        assert items[0].missing_fields == (CompetencyMatrixMissingFieldEnum.ANSWER_EN,)

    async def test_list_workspace_items_supports_filters_and_all_sorts(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="searchable-ready-python",
                    published_at="2024-02-01T00:00:00",
                    question="Searchable Python Queue",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    subsection_id=3,
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Async",
                ),
                self.factory.core.competency_matrix_item(
                    item_id=4,
                    slug="searchable-missing-python",
                    published_at="2024-02-15T00:00:00",
                    question="Searchable Python Missing",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    answer_en="",
                    subsection_id=3,
                    sheet="Python",
                    grade=GradeEnum.MIDDLE,
                    section="Basics",
                    subsection="Async",
                ),
            ],
        )

        for sort in CompetencyMatrixWorkspaceSortEnum:
            items, total_count, summary = await self.storage.list_competency_matrix_workspace_items(
                filters=CompetencyMatrixWorkspaceFilters(
                    page=1,
                    page_size=10,
                    language=LanguageEnum.EN,
                    sort=sort,
                    search_query="searchable python",
                    sheet_keys=("python",),
                    grades=(),
                    sections=("Basics",),
                    subsections=("Async",),
                    publish_statuses=(PublishStatusEnum.PUBLISHED,),
                    published_from=None,
                    published_to=None,
                    has_missing_fields=None,
                ),
            )

            assert total_count == 2
            assert summary.total == 2
            assert set(self.collections.slugs(items)) == {
                "searchable-ready-python",
                "searchable-missing-python",
            }

        (
            missing_items,
            missing_total,
            missing_summary,
        ) = await self.storage.list_competency_matrix_workspace_items(
            filters=CompetencyMatrixWorkspaceFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                sort=CompetencyMatrixWorkspaceSortEnum.MISSING_FIELDS,
                search_query="searchable",
                sheet_keys=("python",),
                grades=(),
                sections=("Basics",),
                subsections=("Async",),
                publish_statuses=(PublishStatusEnum.PUBLISHED,),
                published_from=None,
                published_to=None,
                has_missing_fields=True,
            ),
        )
        assert missing_total == 1
        assert missing_summary.dangerous_published == 1
        assert self.collections.slugs(missing_items) == ["searchable-missing-python"]

        (
            date_items,
            date_total,
            _summary,
        ) = await self.storage.list_competency_matrix_workspace_items(
            filters=CompetencyMatrixWorkspaceFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                sort=CompetencyMatrixWorkspaceSortEnum.NEWEST,
                search_query="searchable",
                sheet_keys=("python",),
                grades=(),
                sections=("Basics",),
                subsections=("Async",),
                publish_statuses=(PublishStatusEnum.PUBLISHED,),
                published_from=datetime(2024, 2, 10, tzinfo=UTC).date(),
                published_to=datetime(2024, 2, 20, tzinfo=UTC).date(),
                has_missing_fields=None,
            ),
        )
        assert date_total == 1
        assert self.collections.slugs(date_items) == ["searchable-missing-python"]

    async def test_list_workspace_filter_options_includes_admin_visible_values(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="draft-option-python",
                    question="Draft option",
                    publish_status=PublishStatusEnum.DRAFT,
                    sheet_id=3,
                    section_id=3,
                    subsection_id=4,
                    sheet_key="python-draft",
                    sheet_ru="Питон черновик",
                    sheet_en="Python draft",
                    grade=GradeEnum.JUNIOR,
                    section_ru="Черновики",
                    section_en="Drafts",
                    subsection_ru="Очередь",
                    subsection_en="Queue",
                ),
            ],
        )

        options = await self.storage.list_competency_matrix_workspace_filter_options(
            language=LanguageEnum.EN,
        )

        assert self.collections.sheet_keys(options.sheets) == ["python", "sql", "python-draft"]
        assert self.collections.pluck(
            items=options.sheets,
            attr="label",
        ) == ["Python", "SQL", "Python draft"]
        python_draft = next(sheet for sheet in options.sheets if sheet.key == "python-draft")
        assert [
            (
                section.id,
                section.label,
                [(subsection.id, subsection.label) for subsection in section.subsections],
            )
            for section in python_draft.sections
        ] == [
            (
                self.factory.core.hex_id(3),
                "Drafts",
                [(self.factory.core.hex_id(4), "Queue")],
            ),
        ]
        assert GradeEnum.JUNIOR in options.grades
        assert InterviewFrequencyEnum.OFTEN in options.interview_frequencies
        assert "Drafts" in options.sections
        assert "Queue" in options.subsections
        assert PublishStatusEnum.DRAFT in options.publish_statuses
        assert PublishStatusEnum.PUBLISHED in options.publish_statuses

    async def test_list_workspace_items_filters_by_structure_ids_in_any_language(self) -> None:
        expected_slugs = ["1"]
        for language in LanguageEnum:
            items, total_count, summary = await self.storage.list_competency_matrix_workspace_items(
                filters=CompetencyMatrixWorkspaceFilters(
                    page=1,
                    page_size=20,
                    language=language,
                    sort=CompetencyMatrixWorkspaceSortEnum.NEWEST,
                    section_ids=(self.factory.core.hex_id(1),),
                    subsection_ids=(self.factory.core.hex_id(1),),
                ),
            )

            assert total_count == 1
            assert summary.total == 1
            assert self.collections.slugs(items) == expected_slugs

    async def test_list_workspace_items_filters_and_sorts_by_interview_frequency(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=10,
                    slug="constant-question",
                    question="Constant question",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                    interview_frequency=InterviewFrequencyEnum.CONSTANTLY,
                ),
                self.factory.core.competency_matrix_item(
                    item_id=11,
                    slug="often-question",
                    question="Often question",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                    interview_frequency=InterviewFrequencyEnum.OFTEN,
                ),
                self.factory.core.competency_matrix_item(
                    item_id=12,
                    slug="rare-question",
                    question="Rare question",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                    interview_frequency=InterviewFrequencyEnum.RARELY,
                ),
                self.factory.core.competency_matrix_item(
                    item_id=13,
                    slug="never-seen-question",
                    question="Never seen question",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                    interview_frequency=InterviewFrequencyEnum.NEVER_SEEN,
                ),
                self.factory.core.competency_matrix_item(
                    item_id=14,
                    slug="empty-frequency-question",
                    question="Empty frequency question",
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                    interview_frequency=None,
                ),
            ],
        )

        (
            filtered_items,
            filtered_total,
            _summary,
        ) = await self.storage.list_competency_matrix_workspace_items(
            filters=CompetencyMatrixWorkspaceFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                sort=CompetencyMatrixWorkspaceSortEnum.INTERVIEW_FREQUENCY,
                search_query="question",
                sheet_keys=("python",),
                grades=(),
                interview_frequencies=(
                    InterviewFrequencyEnum.RARELY,
                    InterviewFrequencyEnum.NEVER_SEEN,
                ),
                sections=("Basics",),
                subsections=("Functions",),
                publish_statuses=(),
                published_from=None,
                published_to=None,
                has_missing_fields=None,
            ),
        )

        assert filtered_total == 2
        assert [item.slug for item in filtered_items] == [
            "rare-question",
            "never-seen-question",
        ]
        assert filtered_items[0].interview_frequency == InterviewFrequencyEnum.RARELY

        (
            sorted_items,
            sorted_total,
            _summary,
        ) = await self.storage.list_competency_matrix_workspace_items(
            filters=CompetencyMatrixWorkspaceFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                sort=CompetencyMatrixWorkspaceSortEnum.INTERVIEW_FREQUENCY,
                search_query="question",
                sheet_keys=("python",),
                grades=(),
                interview_frequencies=(),
                sections=("Basics",),
                subsections=("Functions",),
                publish_statuses=(),
                published_from=None,
                published_to=None,
                has_missing_fields=None,
            ),
        )

        assert sorted_total == 5
        assert [item.slug for item in sorted_items] == [
            "constant-question",
            "often-question",
            "rare-question",
            "never-seen-question",
            "empty-frequency-question",
        ]

    async def test_create_competency_matrix_item_allows_draft_without_grade(self) -> None:
        item = await self.storage.create_competency_matrix_item(
            item=self.factory.core.competency_matrix_item(
                item_id=7,
                slug="draft-without-grade",
                question_ru="Черновик без грейда",
                question_en="Draft without grade",
                publish_status=PublishStatusEnum.DRAFT,
                answer_ru="",
                answer_en="",
                interview_answer_explanation_ru="",
                interview_answer_explanation_en="",
                grade=None,
            ),
        )

        assert item.grade is None
        assert item.missing_publication_fields() == (
            CompetencyMatrixMissingFieldEnum.GRADE,
            CompetencyMatrixMissingFieldEnum.ANSWER_RU,
            CompetencyMatrixMissingFieldEnum.ANSWER_EN,
            CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_RU,
            CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_EN,
        )

    async def test_create_competency_matrix_item(self) -> None:
        item = await self.storage.create_competency_matrix_item(
            item=self.factory.core.competency_matrix_item(
                item_id=3,
                slug="created-question",
                published_at="2024-01-01T00:00:00",
                question="1",
                answer="Answer 1",
                interview_answer_explanation="Answer explanation 1",
                sheet="Python",
                grade=GradeEnum.MIDDLE_PLUS,
                section="Basics",
                subsection="Functions",
                resources=[
                    self.factory.core.attached_external_resource(
                        resource_id=10,
                        name="NAME 1",
                        url="https://example1.com",
                        context="CONTEXT 1",
                    ),
                ],
            ),
        )
        assert item == self.factory.core.competency_matrix_item(
            item_id=3,
            slug="created-question",
            published_at="2024-01-01T00:00:00",
            question="1",
            answer="Answer 1",
            interview_answer_explanation="Answer explanation 1",
            sheet="Python",
            grade=GradeEnum.MIDDLE_PLUS,
            section="Basics",
            subsection="Functions",
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=10,
                    name="NAME 1",
                    url="https://example1.com",
                    context="CONTEXT 1",
                ),
            ],
        )

    async def test_create_competency_matrix_item_maps_duplicate_slug_to_conflict(self) -> None:
        with pytest.raises(CompetencyMatrixItemConflictError):
            await self.storage.create_competency_matrix_item(
                item=self.factory.core.competency_matrix_item(
                    item_id=99,
                    slug="1",
                    question="Duplicate slug",
                ),
            )

    async def test_update_competency_matrix_item(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="existing-question-to-update",
                    question="1",
                    answer="Answer 1",
                    interview_answer_explanation="Answer explanation 1",
                    sheet="Python",
                    grade=GradeEnum.MIDDLE_PLUS,
                    section="Basics",
                    subsection="Functions",
                    resources=[
                        self.factory.core.attached_external_resource(
                            resource_id=10,
                            name="NAME 1",
                            url="https://example1.com",
                            context="CONTEXT 1",
                        ),
                    ],
                ),
            ],
        )
        await self.storage_helper.create_competency_matrix_structure(
            structure=self.factory.core.competency_matrix_item_structure(
                sheet_id=3,
                sheet_key="python-2",
                sheet_ru="Python 2",
                sheet_en="Python 2",
                section_id=3,
                section_ru="SECTION 3",
                section_en="SECTION 3",
                subsection_id=5,
                subsection_ru="SUBSECTION 3",
                subsection_en="SUBSECTION 3",
            ),
        )
        item = await self.storage.update_competency_matrix_item(
            item=self.factory.core.competency_matrix_item(
                item_id=3,
                sheet_id=3,
                section_id=3,
                subsection_id=5,
                slug="updated-question",
                published_at="2024-01-02T00:00:00",
                question="3",
                answer="Answer 3",
                interview_answer_explanation="Answer explanation 3",
                sheet="Python 2",
                grade=GradeEnum.SENIOR,
                section="SECTION 3",
                subsection="SUBSECTION 3",
                resources=[
                    self.factory.core.attached_external_resource(
                        resource_id=10,
                        name="NAME 3",
                        url="https://example3.com",
                        context="CONTEXT 3",
                    ),
                ],
            ),
        )
        assert item == self.factory.core.competency_matrix_item(
            item_id=3,
            sheet_id=3,
            section_id=3,
            subsection_id=5,
            slug="updated-question",
            published_at="2024-01-02T00:00:00",
            question="3",
            answer="Answer 3",
            interview_answer_explanation="Answer explanation 3",
            sheet="Python 2",
            grade=GradeEnum.SENIOR,
            section="SECTION 3",
            subsection="SUBSECTION 3",
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=10,
                    name="NAME 3",
                    url="https://example3.com",
                    context="CONTEXT 3",
                ),
            ],
        )

    async def test_update_competency_matrix_item_replaces_resources(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="existing-question-with-resources",
                    question="1",
                    answer="Answer 1",
                    interview_answer_explanation="Answer explanation 1",
                    sheet="Python",
                    grade=GradeEnum.MIDDLE_PLUS,
                    section="Basics",
                    subsection="Functions",
                    resources=[
                        self.factory.core.attached_external_resource(
                            resource_id=10,
                            name="NAME 10",
                            url="https://example10.com",
                            context="CONTEXT 10",
                        ),
                        self.factory.core.attached_external_resource(
                            resource_id=11,
                            name="NAME 11",
                            url="https://example11.com",
                            context="CONTEXT 11",
                        ),
                    ],
                ),
            ],
        )
        item = await self.storage.update_competency_matrix_item(
            item=self.factory.core.competency_matrix_item(
                item_id=3,
                slug="updated-question-with-resources",
                question="1",
                answer="Answer 1",
                interview_answer_explanation="Answer explanation 1",
                sheet="Python",
                grade=GradeEnum.MIDDLE_PLUS,
                section="Basics",
                subsection="Functions",
                resources=[
                    self.factory.core.attached_external_resource(
                        resource_id=12,
                        name="NAME 12",
                        url="https://example12.com",
                        context="CONTEXT 12",
                    ),
                ],
            ),
        )
        assert item.resources.values == [
            self.factory.core.attached_external_resource(
                resource_id=12,
                name="NAME 12",
                url="https://example12.com",
                context="CONTEXT 12",
            ),
        ]

    async def test_update_competency_matrix_item_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.update_competency_matrix_item(
                item=self.factory.core.competency_matrix_item(item_id=3),
            )

    async def test_update_publish_status(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="publish-status-question",
                    question="1",
                    answer="Answer 1",
                    interview_answer_explanation="Answer explanation 1",
                    sheet="Python",
                    grade=GradeEnum.MIDDLE_PLUS,
                    section="Basics",
                    subsection="Functions",
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
            ],
        )
        await self.storage.update_competency_matrix_item_publish_status(
            item_id=self.factory.core.hex_id(3),
            publish_status=PublishStatusEnum.DRAFT,
        )
        item = await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(3))
        assert item.publish_status == PublishStatusEnum.DRAFT

    async def test_update_publish_status_sets_first_published_at_only_once(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="first-publish-question",
                    question="First publish",
                    publish_status=PublishStatusEnum.DRAFT,
                    sheet="Python",
                    grade=GradeEnum.JUNIOR,
                    section="Basics",
                    subsection="Functions",
                ),
            ],
        )

        await self.storage.update_competency_matrix_item_publish_status(
            item_id=self.factory.core.hex_id(3),
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        first = await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(3))
        await self.storage.update_competency_matrix_item_publish_status(
            item_id=self.factory.core.hex_id(3),
            publish_status=PublishStatusEnum.DRAFT,
        )
        await self.storage.update_competency_matrix_item_publish_status(
            item_id=self.factory.core.hex_id(3),
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        second = await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(3))

        assert first.published_at is not None
        assert second.published_at == first.published_at

    async def test_update_publish_status_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.update_competency_matrix_item_publish_status(
                item_id=self.factory.core.hex_id(3),
                publish_status=PublishStatusEnum.DRAFT,
            )

    async def test_get_resources_by_ids(self) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=100,
                    name="NAME 100",
                    url="https://example100.com",
                ),
                self.factory.core.external_resource(
                    resource_id=101,
                    name="NAME 101",
                    url="https://example101.com",
                ),
            ],
        )
        resources = await self.storage.get_resources_by_ids(
            resource_ids=[self.factory.core.hex_id(100), self.factory.core.hex_id(101)]
        )
        assert resources.values == [
            self.factory.core.external_resource(
                resource_id=100,
                name="NAME 100",
                url="https://example100.com",
            ),
            self.factory.core.external_resource(
                resource_id=101,
                name="NAME 101",
                url="https://example101.com",
            ),
        ]

    async def test_delete_found(self) -> None:
        await self.storage_helper.create_competency_matrix_items(
            items=[
                self.factory.core.competency_matrix_item(
                    item_id=3,
                    slug="delete-question",
                    question="1",
                    answer="Answer 1",
                    interview_answer_explanation="Answer explanation 1",
                    sheet="Python",
                    grade=GradeEnum.MIDDLE_PLUS,
                    section="Basics",
                    subsection="Functions",
                    resources=[
                        self.factory.core.attached_external_resource(
                            resource_id=10,
                            name="NAME 1",
                            url="https://example1.com",
                            context="CONTEXT 1",
                        ),
                    ],
                ),
            ],
        )
        await self.storage.delete_competency_matrix_item(item_id=self.factory.core.hex_id(3))
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.get_competency_matrix_item(item_id=self.factory.core.hex_id(3))

    async def test_delete_not_found(self) -> None:
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.storage.delete_competency_matrix_item(item_id=self.factory.core.hex_id(3))

    async def test_search_competency_matrix_resources(self) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=100,
                    name="NAMED 100",
                    url="https://example100.com",
                ),
                self.factory.core.external_resource(
                    resource_id=101,
                    name="NAMED 101",
                    url="https://example101.com",
                ),
                self.factory.core.external_resource(
                    resource_id=102,
                    name="NOT HAS N*MED",
                    url="https://example102.com",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="named",
            limit=10,
            language=LanguageEnum.EN,
        )
        assert len(resources) == 2
        assert resources[0].name_en == "NAMED 100"
        assert resources[1].name_en == "NAMED 101"

    async def test_search_competency_matrix_resources_matches_typo(self) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=110,
                    name="Pydantic",
                    url="https://docs.pydantic.dev",
                ),
                self.factory.core.external_resource(
                    resource_id=111,
                    name="Django",
                    url="https://docs.djangoproject.com",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="pydntic",
            limit=10,
            language=LanguageEnum.EN,
        )
        assert self.collections.names_en(resources) == ["Pydantic"]

    async def test_search_competency_matrix_resources_matches_url(self) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=115,
                    name="Validation documentation",
                    url="https://docs.pydantic.dev/latest/",
                ),
                self.factory.core.external_resource(
                    resource_id=116,
                    name="Web framework documentation",
                    url="https://docs.djangoproject.com",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="pydantic.dev",
            limit=10,
            language=LanguageEnum.EN,
        )
        assert self.collections.names_en(resources) == ["Validation documentation"]

    async def test_search_competency_matrix_resources_matches_secondary_language_name(
        self,
    ) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=120,
                    name_ru="Документация FastAPI",
                    name_en="FastAPI docs",
                    url="https://fastapi.tiangolo.com",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="документация",
            limit=10,
            language=LanguageEnum.EN,
        )
        assert self.collections.names_en(resources) == ["FastAPI docs"]

    async def test_search_competency_matrix_resources_ranks_active_language_matches(
        self,
    ) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=130,
                    name="Python Package Index",
                    url="https://pypi.org",
                ),
                self.factory.core.external_resource(
                    resource_id=131,
                    name="Packaging guide",
                    url="https://python.example.com/packages",
                ),
                self.factory.core.external_resource(
                    resource_id=132,
                    name="Python",
                    url="https://python.org",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="python",
            limit=10,
            language=LanguageEnum.EN,
        )
        assert self.collections.names_en(resources)[:2] == [
            "Python",
            "Python Package Index",
        ]

    async def test_search_competency_matrix_resources_respects_limit(self) -> None:
        await self.storage_helper.create_external_resources(
            resources=[
                self.factory.core.external_resource(
                    resource_id=140,
                    name="Limit resource A",
                    url="https://example-a.com",
                ),
                self.factory.core.external_resource(
                    resource_id=141,
                    name="Limit resource B",
                    url="https://example-b.com",
                ),
                self.factory.core.external_resource(
                    resource_id=142,
                    name="Limit resource C",
                    url="https://example-c.com",
                ),
            ],
        )
        resources = await self.storage.search_competency_matrix_resources(
            search_name="limit",
            limit=2,
            language=LanguageEnum.EN,
        )
        assert len(resources) == 2
