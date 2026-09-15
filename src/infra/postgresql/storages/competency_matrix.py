from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, cast

from sqlalchemy import (
    ARRAY,
    Select,
    String,
    and_,
    bindparam,
    case,
    delete,
    func,
    or_,
    select,
    union,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, defer, selectinload
from sqlalchemy.sql.elements import ColumnElement

from core.competency_matrix.enums import (
    CompetencyMatrixWorkspaceSortEnum,
    InterviewFrequencyEnum,
)
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemConflictError,
    CompetencyMatrixItemNotFoundError,
    CompetencyMatrixStructureAlreadyExistsError,
    CompetencyMatrixStructureNotFoundError,
    QueuedCompetencyMatrixQuestionNotFoundError,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixFilterOptions,
    CompetencyMatrixFilterSectionOption,
    CompetencyMatrixFilterSheetOption,
    CompetencyMatrixFilterSubsectionOption,
    CompetencyMatrixItem,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItemStructure,
    CompetencyMatrixMissingFieldEnum,
    CompetencyMatrixQuestionFingerprint,
    CompetencyMatrixSectionCreateParams,
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetCreateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    CompetencyMatrixSubsectionCreateParams,
    CompetencyMatrixSubsectionPriorityUpdateParams,
    CompetencyMatrixWorkspaceFilters,
    CompetencyMatrixWorkspaceItem,
    CompetencyMatrixWorkspaceSummary,
    ExternalResources,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
    QueuedCompetencyMatrixQuestionsCreateParams,
    Sheet,
    Sheets,
)
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from infra.config.constants import constants
from infra.postgresql.models import (
    AgentClientModel,
    CompetencyMatrixItemModel,
    CompetencyMatrixSectionModel,
    CompetencyMatrixSheetModel,
    CompetencyMatrixSubsectionModel,
    ExternalResourceModel,
    MatrixQuestionClaimModel,
)
from infra.postgresql.models.competency_matrix import (
    QueuedQuestionModel,
    ResourceToItemSecondaryModel,
)

type PriorityStructureModel = type[
    CompetencyMatrixSheetModel | CompetencyMatrixSectionModel | CompetencyMatrixSubsectionModel
]


@dataclass(kw_only=True)
class CompetencyMatrixDatabaseStorage(CompetencyMatrixStorage):
    session: AsyncSession

    async def list_sheets(self) -> Sheets:
        stmt = (
            select(CompetencyMatrixSheetModel)
            .join(CompetencyMatrixSheetModel.sections)
            .join(CompetencyMatrixSectionModel.subsections)
            .join(CompetencyMatrixSubsectionModel.items)
            .where(CompetencyMatrixItemModel.publish_status == PublishStatusEnum.PUBLISHED)
            .distinct()
            .order_by(CompetencyMatrixSheetModel.priority, CompetencyMatrixSheetModel.id)
        )
        sheets = await self.session.scalars(stmt)
        return Sheets(
            values=[
                Sheet(key=sheet.key, name_ru=sheet.name_ru, name_en=sheet.name_en)
                for sheet in sheets
            ],
        )

    async def list_structure(self) -> CompetencyMatrixStructure:
        stmt = (
            select(CompetencyMatrixSheetModel)
            .options(
                selectinload(CompetencyMatrixSheetModel.sections).selectinload(
                    CompetencyMatrixSectionModel.subsections,
                ),
            )
            .order_by(CompetencyMatrixSheetModel.priority, CompetencyMatrixSheetModel.id)
        )
        sheets = await self.session.scalars(stmt)
        return CompetencyMatrixStructure(
            sheets=[sheet.to_domain_schema() for sheet in sheets],
        )

    async def get_item_structure_by_subsection_id(
        self,
        *,
        subsection_id: str,
    ) -> CompetencyMatrixItemStructure:
        subsection = await self._get_subsection_model(subsection_id=subsection_id)
        return subsection.to_item_structure()

    async def create_sheet(
        self,
        *,
        params: CompetencyMatrixSheetCreateParams,
    ) -> CompetencyMatrixStructureSheet:
        if await self._sheet_exists_by_key(key=params.key):
            raise CompetencyMatrixStructureAlreadyExistsError
        sheet = CompetencyMatrixSheetModel(
            key=params.key,
            name_ru=params.name_ru,
            name_en=params.name_en,
            priority=await self._next_sheet_priority(),
        )
        self.session.add(sheet)
        await self.session.flush()
        return CompetencyMatrixStructureSheet(
            id=sheet.id,
            key=sheet.key,
            name_ru=sheet.name_ru,
            name_en=sheet.name_en,
            priority=sheet.priority,
            sections=[],
        )

    async def create_section(
        self,
        *,
        params: CompetencyMatrixSectionCreateParams,
    ) -> CompetencyMatrixStructureSection:
        await self._get_sheet_model(sheet_id=params.sheet_id)
        if await self._section_exists_by_name(params=params):
            raise CompetencyMatrixStructureAlreadyExistsError
        section = CompetencyMatrixSectionModel(
            sheet_id=params.sheet_id,
            name_ru=params.name_ru,
            name_en=params.name_en,
            priority=await self._next_section_priority(sheet_id=params.sheet_id),
        )
        self.session.add(section)
        await self.session.flush()
        return CompetencyMatrixStructureSection(
            id=section.id,
            name_ru=section.name_ru,
            name_en=section.name_en,
            priority=section.priority,
            subsections=[],
        )

    async def create_subsection(
        self,
        *,
        params: CompetencyMatrixSubsectionCreateParams,
    ) -> CompetencyMatrixStructureSubsection:
        await self._get_section_model(section_id=params.section_id)
        if await self._subsection_exists_by_name(params=params):
            raise CompetencyMatrixStructureAlreadyExistsError
        subsection = CompetencyMatrixSubsectionModel(
            section_id=params.section_id,
            name_ru=params.name_ru,
            name_en=params.name_en,
            priority=await self._next_subsection_priority(section_id=params.section_id),
        )
        self.session.add(subsection)
        await self.session.flush()
        return CompetencyMatrixStructureSubsection(
            id=subsection.id,
            name_ru=subsection.name_ru,
            name_en=subsection.name_en,
            priority=subsection.priority,
        )

    async def update_sheet_priorities(
        self,
        *,
        params: CompetencyMatrixSheetPriorityUpdateParams,
    ) -> None:
        await self._update_priorities(
            model=CompetencyMatrixSheetModel,
            ordered_ids=params.ordered_ids,
        )

    async def update_section_priorities(
        self,
        *,
        params: CompetencyMatrixSectionPriorityUpdateParams,
    ) -> None:
        await self._update_priorities(
            model=CompetencyMatrixSectionModel,
            ordered_ids=params.ordered_ids,
        )

    async def update_subsection_priorities(
        self,
        *,
        params: CompetencyMatrixSubsectionPriorityUpdateParams,
    ) -> None:
        await self._update_priorities(
            model=CompetencyMatrixSubsectionModel,
            ordered_ids=params.ordered_ids,
        )

    async def list_competency_matrix_items(
        self,
        *,
        filters: CompetencyMatrixItemFilters,
    ) -> list[CompetencyMatrixItem]:
        stmt = self._select_items_with_structure().order_by(
            CompetencyMatrixSheetModel.priority,
            CompetencyMatrixSheetModel.id,
            CompetencyMatrixSectionModel.priority,
            CompetencyMatrixSectionModel.id,
            CompetencyMatrixSubsectionModel.priority,
            CompetencyMatrixSubsectionModel.id,
            CompetencyMatrixItemModel.grade,
            CompetencyMatrixItemModel.id,
        )
        if filters.sheet_key is not None:
            stmt = stmt.where(
                func.lower(CompetencyMatrixSheetModel.key) == filters.sheet_key.lower(),
            )
        if filters.only_published is True:
            stmt = stmt.where(
                CompetencyMatrixItemModel.publish_status == PublishStatusEnum.PUBLISHED,
            )
        items = await self.session.scalars(stmt)
        return [item.to_domain_schema(include_relationships=False) for item in items]

    async def list_competency_matrix_workspace_items(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> tuple[
        list[CompetencyMatrixWorkspaceItem],
        int,
        CompetencyMatrixWorkspaceSummary,
    ]:
        stmt = self._apply_workspace_filters(
            self._select_items_with_structure(),
            filters=filters,
        ).order_by(*self._workspace_ordering(filters=filters))
        items = await self.session.scalars(stmt.offset(filters.offset).limit(filters.limit))
        count_stmt = self._apply_workspace_filters(
            self._join_structure(select(func.count(CompetencyMatrixItemModel.id))),
            filters=filters,
        )
        total_count = (await self.session.scalar(count_stmt)) or 0
        summary = await self._workspace_summary(filters=filters)
        return (
            [self._to_workspace_item(item=item, language=filters.language) for item in items],
            total_count,
            summary,
        )

    async def list_competency_matrix_workspace_filter_options(
        self,
        *,
        language: LanguageEnum,
    ) -> CompetencyMatrixFilterOptions:
        sheet_name_column = self._sheet_column(language=language)
        section_column = self._section_column(language=language)
        subsection_column = self._subsection_column(language=language)
        sheets_rows = await self.session.execute(
            self._join_structure_nodes_with_items(
                select(
                    CompetencyMatrixSheetModel.key.label("sheet_key"),
                    sheet_name_column.label("sheet"),
                    section_column.label("section"),
                    subsection_column.label("subsection"),
                    CompetencyMatrixSheetModel.priority.label("sheet_priority"),
                    CompetencyMatrixSheetModel.id.label("sheet_id"),
                    CompetencyMatrixSectionModel.priority.label("section_priority"),
                    CompetencyMatrixSectionModel.id.label("section_id"),
                    CompetencyMatrixSubsectionModel.priority.label("subsection_priority"),
                    CompetencyMatrixSubsectionModel.id.label("subsection_id"),
                ),
            )
            .distinct()
            .order_by(
                CompetencyMatrixSheetModel.priority,
                CompetencyMatrixSheetModel.id,
                CompetencyMatrixSectionModel.priority,
                CompetencyMatrixSectionModel.id,
                CompetencyMatrixSubsectionModel.priority,
                CompetencyMatrixSubsectionModel.id,
            ),
        )
        grades = await self.session.scalars(
            select(CompetencyMatrixItemModel.grade)
            .distinct()
            .order_by(CompetencyMatrixItemModel.grade),
        )
        interview_frequencies = await self.session.scalars(
            select(CompetencyMatrixItemModel.interview_frequency).distinct(),
        )
        sections = await self.session.scalars(
            self._join_structure_nodes_with_items(select(section_column))
            .distinct()
            .order_by(section_column),
        )
        subsections = await self.session.scalars(
            self._join_structure_nodes_with_items(select(subsection_column))
            .distinct()
            .order_by(subsection_column),
        )
        publish_statuses = await self.session.scalars(
            select(CompetencyMatrixItemModel.publish_status)
            .distinct()
            .order_by(CompetencyMatrixItemModel.publish_status),
        )
        return CompetencyMatrixFilterOptions(
            sheets=self._workspace_filter_sheet_options(rows=list(sheets_rows)),
            grades=[grade for grade in grades if grade is not None],
            interview_frequencies=self._ordered_interview_frequencies(
                values=[frequency for frequency in interview_frequencies if frequency is not None],
            ),
            sections=[section for section in sections if section],
            subsections=[subsection for subsection in subsections if subsection],
            publish_statuses=[
                PublishStatusEnum.from_storage_value(publish_status)
                for publish_status in publish_statuses
            ],
        )

    def _workspace_filter_sheet_options(
        self,
        *,
        rows: list[Any],
    ) -> list[CompetencyMatrixFilterSheetOption]:
        sheets: dict[str, dict[str, Any]] = {}
        for row in rows:
            sheet = sheets.setdefault(
                row.sheet_key,
                {"label": row.sheet, "sections": {}},
            )
            if not row.section:
                continue
            section = sheet["sections"].setdefault(
                row.section_id,
                {"label": row.section, "subsections": {}},
            )
            if row.subsection:
                section["subsections"].setdefault(row.subsection_id, row.subsection)
        return [
            CompetencyMatrixFilterSheetOption(
                key=sheet_key,
                label=sheet["label"],
                sections=[
                    CompetencyMatrixFilterSectionOption(
                        id=section_id,
                        label=section["label"],
                        subsections=[
                            CompetencyMatrixFilterSubsectionOption(
                                id=subsection_id,
                                label=subsection_label,
                            )
                            for subsection_id, subsection_label in section["subsections"].items()
                        ],
                    )
                    for section_id, section in sheet["sections"].items()
                ],
            )
            for sheet_key, sheet in sheets.items()
        ]

    async def get_competency_matrix_item(self, item_id: str) -> CompetencyMatrixItem:
        stmt = (
            select(CompetencyMatrixItemModel)
            .where(CompetencyMatrixItemModel.id == item_id)
            .options(
                *self._item_domain_load_options(),
                *self._item_structure_load_options(),
                selectinload(CompetencyMatrixItemModel.resource_links).selectinload(
                    ResourceToItemSecondaryModel.resource,
                ),
            )
        )
        item = await self.session.scalar(stmt)
        if item is None:
            raise CompetencyMatrixItemNotFoundError
        return item.to_domain_schema(include_relationships=True)

    async def get_competency_matrix_item_by_slug(self, slug: str) -> CompetencyMatrixItem:
        stmt = (
            select(CompetencyMatrixItemModel)
            .where(CompetencyMatrixItemModel.slug == slug)
            .options(
                *self._item_domain_load_options(),
                *self._item_structure_load_options(),
                selectinload(CompetencyMatrixItemModel.resource_links).selectinload(
                    ResourceToItemSecondaryModel.resource,
                ),
            )
        )
        item = await self.session.scalar(stmt)
        if item is None:
            raise CompetencyMatrixItemNotFoundError
        return item.to_domain_schema(include_relationships=True)

    async def create_competency_matrix_item(
        self,
        item: CompetencyMatrixItem,
    ) -> CompetencyMatrixItem:
        item_model = CompetencyMatrixItemModel.from_domain_schema(
            item=item,
            include_relationships=False,
        )
        self._ensure_first_published_at(item_model=item_model)
        item_model.resource_links = await self._build_resource_links(
            item=item,
            existing_links=None,
        )
        self.session.add(item_model)
        try:
            await self.session.flush()
        except IntegrityError as error:
            diagnostics = getattr(error.orig, "diag", None)
            constraint_name = getattr(diagnostics, "constraint_name", None)
            if constraint_name == "ix_competency_matrix__competency_matrix_item_model_slug":
                raise CompetencyMatrixItemConflictError from error
            if isinstance(constraint_name, str) and constraint_name.endswith(
                "_subsection_id_fkey",
            ):
                raise CompetencyMatrixStructureNotFoundError from error
            if isinstance(constraint_name, str) and constraint_name.endswith(
                "_resource_id_fkey",
            ):
                raise CompetencyMatrixItemNotFoundError from error
            raise
        return await self.get_competency_matrix_item(item_id=item.id)

    async def update_competency_matrix_item(
        self,
        item: CompetencyMatrixItem,
    ) -> CompetencyMatrixItem:
        item_model = await self._get_competency_matrix_item_model(
            item_id=item.id,
            load_resource_links=True,
        )
        item_model.update_from_domain_schema(item=item)
        self._ensure_first_published_at(item_model=item_model)
        item_model.resource_links = await self._build_resource_links(
            item=item,
            existing_links=item_model.resource_links,
        )
        await self.session.flush()
        return await self.get_competency_matrix_item(item_id=item.id)

    async def update_competency_matrix_item_publish_status(
        self,
        item_id: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        item_model = await self._get_competency_matrix_item_model(
            item_id=item_id,
            load_resource_links=False,
        )
        item_model.publish_status = publish_status
        self._ensure_first_published_at(item_model=item_model)
        await self.session.flush()

    async def _get_competency_matrix_item_model(
        self,
        item_id: str,
        *,
        load_resource_links: bool,
    ) -> CompetencyMatrixItemModel:
        stmt = select(CompetencyMatrixItemModel).where(CompetencyMatrixItemModel.id == item_id)
        stmt = stmt.options(*self._item_domain_load_options())
        if load_resource_links:
            stmt = stmt.options(selectinload(CompetencyMatrixItemModel.resource_links))
        item_model = await self.session.scalar(stmt)
        if item_model is None:
            raise CompetencyMatrixItemNotFoundError
        return item_model

    async def _build_resource_links(
        self,
        item: CompetencyMatrixItem,
        existing_links: list[ResourceToItemSecondaryModel] | None,
    ) -> list[ResourceToItemSecondaryModel]:
        links: list[ResourceToItemSecondaryModel] = []
        existing_links_by_resource_id = {link.resource_id: link for link in existing_links or []}
        for resource in item.resources:
            resource_model = await self.session.merge(
                ExternalResourceModel.from_domain_schema(
                    schema=resource.to_external_resource(),
                ),
            )
            link = existing_links_by_resource_id.get(resource.id)
            if link is None:
                link = ResourceToItemSecondaryModel(resource_id=resource.id)
            link.resource = resource_model
            link.context_ru = resource.context_ru
            link.context_en = resource.context_en
            links.append(link)
        return links

    def _select_items_with_structure(self) -> Select[tuple[CompetencyMatrixItemModel]]:
        return self._join_structure(select(CompetencyMatrixItemModel)).options(
            *self._item_domain_load_options(),
            *self._item_structure_load_options(),
        )

    def _item_domain_load_options(self) -> tuple[Any, ...]:
        return (
            defer(CompetencyMatrixItemModel.question_ru_fingerprint),
            defer(CompetencyMatrixItemModel.question_en_fingerprint),
        )

    def _join_structure(self, stmt: Select[Any]) -> Select[Any]:
        return (
            stmt.select_from(CompetencyMatrixItemModel)
            .join(CompetencyMatrixItemModel.subsection)
            .join(CompetencyMatrixSubsectionModel.section)
            .join(CompetencyMatrixSectionModel.sheet)
        )

    def _join_structure_nodes_with_items(self, stmt: Select[Any]) -> Select[Any]:
        return (
            stmt.select_from(CompetencyMatrixSheetModel)
            .join(CompetencyMatrixSheetModel.sections)
            .join(CompetencyMatrixSectionModel.subsections)
            .where(self._subsection_has_items_condition())
        )

    def _subsection_has_items_condition(self) -> ColumnElement[bool]:
        return (
            select(CompetencyMatrixItemModel.id)
            .where(CompetencyMatrixItemModel.subsection_id == CompetencyMatrixSubsectionModel.id)
            .exists()
        )

    def _item_structure_load_options(self) -> tuple[Any, ...]:
        return (
            selectinload(CompetencyMatrixItemModel.subsection)
            .selectinload(CompetencyMatrixSubsectionModel.section)
            .selectinload(CompetencyMatrixSectionModel.sheet),
        )

    async def _next_sheet_priority(self) -> int:
        return await self._next_priority(model=CompetencyMatrixSheetModel, conditions=())

    async def _next_section_priority(self, *, sheet_id: str) -> int:
        return await self._next_priority(
            model=CompetencyMatrixSectionModel,
            conditions=(CompetencyMatrixSectionModel.sheet_id == sheet_id,),
        )

    async def _next_subsection_priority(self, *, section_id: str) -> int:
        return await self._next_priority(
            model=CompetencyMatrixSubsectionModel,
            conditions=(CompetencyMatrixSubsectionModel.section_id == section_id,),
        )

    async def _next_priority(
        self,
        *,
        model: PriorityStructureModel,
        conditions: tuple[ColumnElement[bool], ...],
    ) -> int:
        stmt = select(func.coalesce(func.max(model.priority), 0) + 1)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int((await self.session.scalar(stmt)) or 1)

    async def _update_priorities(
        self,
        *,
        model: PriorityStructureModel,
        ordered_ids: tuple[str, ...],
    ) -> None:
        if not ordered_ids:
            return
        priority_by_id = {
            ordered_id: priority for priority, ordered_id in enumerate(ordered_ids, start=1)
        }
        priority_cases = tuple(
            (model.id == ordered_id, priority) for ordered_id, priority in priority_by_id.items()
        )
        await self.session.execute(
            update(model)
            .where(model.id.in_(priority_by_id.keys()))
            .values(
                priority=case(
                    *priority_cases,
                    else_=model.priority,
                ),
            ),
        )

    async def _get_sheet_model(self, *, sheet_id: str) -> CompetencyMatrixSheetModel:
        sheet = await self.session.get(CompetencyMatrixSheetModel, sheet_id)
        if sheet is None:
            raise CompetencyMatrixStructureNotFoundError
        return sheet

    async def _get_section_model(self, *, section_id: str) -> CompetencyMatrixSectionModel:
        section = await self.session.get(CompetencyMatrixSectionModel, section_id)
        if section is None:
            raise CompetencyMatrixStructureNotFoundError
        return section

    async def _get_subsection_model(
        self,
        *,
        subsection_id: str,
    ) -> CompetencyMatrixSubsectionModel:
        stmt = (
            select(CompetencyMatrixSubsectionModel)
            .where(CompetencyMatrixSubsectionModel.id == subsection_id)
            .options(
                selectinload(CompetencyMatrixSubsectionModel.section).selectinload(
                    CompetencyMatrixSectionModel.sheet,
                ),
            )
        )
        subsection = await self.session.scalar(stmt)
        if subsection is None:
            raise CompetencyMatrixStructureNotFoundError
        return subsection

    async def _sheet_exists_by_key(self, *, key: str) -> bool:
        exists_stmt = select(
            select(CompetencyMatrixSheetModel.id)
            .where(func.lower(CompetencyMatrixSheetModel.key) == key.lower())
            .exists(),
        )
        return bool(await self.session.scalar(exists_stmt))

    async def _section_exists_by_name(
        self,
        *,
        params: CompetencyMatrixSectionCreateParams,
    ) -> bool:
        exists_stmt = select(
            select(CompetencyMatrixSectionModel.id)
            .where(
                CompetencyMatrixSectionModel.sheet_id == params.sheet_id,
                or_(
                    func.lower(CompetencyMatrixSectionModel.name_ru) == params.name_ru.lower(),
                    func.lower(CompetencyMatrixSectionModel.name_en) == params.name_en.lower(),
                ),
            )
            .exists(),
        )
        return bool(await self.session.scalar(exists_stmt))

    async def _subsection_exists_by_name(
        self,
        *,
        params: CompetencyMatrixSubsectionCreateParams,
    ) -> bool:
        exists_stmt = select(
            select(CompetencyMatrixSubsectionModel.id)
            .where(
                CompetencyMatrixSubsectionModel.section_id == params.section_id,
                or_(
                    func.lower(CompetencyMatrixSubsectionModel.name_ru) == params.name_ru.lower(),
                    func.lower(CompetencyMatrixSubsectionModel.name_en) == params.name_en.lower(),
                ),
            )
            .exists(),
        )
        return bool(await self.session.scalar(exists_stmt))

    def _apply_workspace_filters(
        self,
        stmt: Select[Any],
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> Select[Any]:
        conditions = self._workspace_filter_conditions(filters=filters)
        return stmt.where(*conditions) if conditions else stmt

    def _workspace_filter_conditions(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> list[ColumnElement[bool]]:
        return [
            *self._workspace_dimension_filter_conditions(filters=filters),
            *self._workspace_state_filter_conditions(filters=filters),
        ]

    def _workspace_dimension_filter_conditions(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.sheet_keys:
            conditions.append(CompetencyMatrixSheetModel.key.in_(filters.sheet_keys))
        if filters.grades:
            conditions.append(CompetencyMatrixItemModel.grade.in_(filters.grades))
        if filters.interview_frequencies:
            conditions.append(
                CompetencyMatrixItemModel.interview_frequency.in_(filters.interview_frequencies),
            )
        if filters.section_ids:
            conditions.append(CompetencyMatrixSectionModel.id.in_(filters.section_ids))
        if filters.subsection_ids:
            conditions.append(CompetencyMatrixSubsectionModel.id.in_(filters.subsection_ids))
        if filters.sections:
            conditions.append(
                self._section_column(language=filters.language).in_(filters.sections),
            )
        if filters.subsections:
            conditions.append(
                self._subsection_column(language=filters.language).in_(filters.subsections),
            )
        if filters.publish_statuses:
            conditions.append(
                CompetencyMatrixItemModel.publish_status.in_(filters.publish_statuses),
            )
        return conditions

    def _workspace_state_filter_conditions(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.published_from is not None:
            conditions.append(
                CompetencyMatrixItemModel.published_at
                >= self._date_start(value=filters.published_from),
            )
        if filters.published_to is not None:
            conditions.append(
                CompetencyMatrixItemModel.published_at
                <= self._date_end(value=filters.published_to),
            )
        if filters.search_query is not None:
            search_pattern = f"%{filters.search_query.lower()}%"
            conditions.append(
                or_(
                    func.lower(CompetencyMatrixItemModel.slug).ilike(search_pattern),
                    func.lower(
                        self._question_column(language=filters.language),
                    ).ilike(search_pattern),
                ),
            )
        if filters.has_missing_fields is True:
            conditions.append(self._workspace_missing_condition())
        if filters.has_missing_fields is False:
            conditions.append(~self._workspace_missing_condition())
        return conditions

    async def _workspace_summary(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> CompetencyMatrixWorkspaceSummary:
        missing_condition = self._workspace_missing_condition()
        draft_condition = CompetencyMatrixItemModel.publish_status == PublishStatusEnum.DRAFT
        published_condition = (
            CompetencyMatrixItemModel.publish_status == PublishStatusEnum.PUBLISHED
        )
        stmt = self._apply_workspace_filters(
            self._join_structure(
                select(
                    func.count(CompetencyMatrixItemModel.id).label("total"),
                    func.sum(case((draft_condition, 1), else_=0)).label("draft"),
                    func.sum(case((and_(draft_condition, missing_condition), 1), else_=0)).label(
                        "missing_draft",
                    ),
                    func.sum(
                        case((and_(published_condition, missing_condition), 1), else_=0),
                    ).label("dangerous_published"),
                    func.sum(
                        case((and_(published_condition, ~missing_condition), 1), else_=0),
                    ).label("ready_published"),
                ),
            ),
            filters=filters,
        )
        row = (await self.session.execute(stmt)).one()
        return CompetencyMatrixWorkspaceSummary(
            total=row.total or 0,
            draft=row.draft or 0,
            missing_draft=row.missing_draft or 0,
            dangerous_published=row.dangerous_published or 0,
            ready_published=row.ready_published or 0,
        )

    def _workspace_ordering(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> tuple[Any, ...]:
        question_column = self._question_column(language=filters.language)
        structure_ordering = (
            CompetencyMatrixSheetModel.priority,
            CompetencyMatrixSheetModel.id,
            CompetencyMatrixSectionModel.priority,
            CompetencyMatrixSectionModel.id,
            CompetencyMatrixSubsectionModel.priority,
            CompetencyMatrixSubsectionModel.id,
        )
        default_ordering = (
            *structure_ordering,
            CompetencyMatrixItemModel.grade,
            CompetencyMatrixItemModel.id,
        )
        dangerous_published = and_(
            CompetencyMatrixItemModel.publish_status == PublishStatusEnum.PUBLISHED,
            self._workspace_missing_condition(),
        )
        ordering_by_sort = {
            CompetencyMatrixWorkspaceSortEnum.GRADE: (
                CompetencyMatrixItemModel.grade,
                *structure_ordering,
                question_column,
                CompetencyMatrixItemModel.id,
            ),
            CompetencyMatrixWorkspaceSortEnum.INTERVIEW_FREQUENCY: (
                self._interview_frequency_ordering(),
                *structure_ordering,
                question_column,
                CompetencyMatrixItemModel.id,
            ),
            CompetencyMatrixWorkspaceSortEnum.SECTION: default_ordering,
            CompetencyMatrixWorkspaceSortEnum.SUBSECTION: (
                CompetencyMatrixSheetModel.priority,
                CompetencyMatrixSheetModel.id,
                CompetencyMatrixSubsectionModel.priority,
                CompetencyMatrixSubsectionModel.id,
                CompetencyMatrixSectionModel.priority,
                CompetencyMatrixSectionModel.id,
                CompetencyMatrixItemModel.grade,
                question_column,
                CompetencyMatrixItemModel.id,
            ),
            CompetencyMatrixWorkspaceSortEnum.NEWEST: (
                CompetencyMatrixItemModel.published_at.desc().nullslast(),
                CompetencyMatrixItemModel.id.desc(),
            ),
            CompetencyMatrixWorkspaceSortEnum.OLDEST: (
                CompetencyMatrixItemModel.published_at.asc().nullslast(),
                CompetencyMatrixItemModel.id,
            ),
            CompetencyMatrixWorkspaceSortEnum.MISSING_FIELDS: (
                self._workspace_missing_count().desc(),
                *structure_ordering,
                CompetencyMatrixItemModel.id,
            ),
            CompetencyMatrixWorkspaceSortEnum.DANGEROUS_PUBLISHED: (
                case((dangerous_published, 0), else_=1),
                CompetencyMatrixItemModel.published_at.desc().nullslast(),
                CompetencyMatrixItemModel.id,
            ),
        }
        return ordering_by_sort[filters.sort]

    def _to_workspace_item(
        self,
        *,
        item: CompetencyMatrixItemModel,
        language: LanguageEnum,
    ) -> CompetencyMatrixWorkspaceItem:
        schema = item.to_domain_schema(include_relationships=False)
        return CompetencyMatrixWorkspaceItem(
            id=schema.id,
            slug=schema.slug,
            question=schema.localized_question(language=language),
            sheet_key=schema.sheet_key,
            sheet=schema.localized_sheet(language=language),
            grade=schema.grade,
            interview_frequency=schema.interview_frequency,
            section=schema.localized_section(language=language),
            subsection=schema.localized_subsection(language=language),
            publish_status=schema.publish_status,
            published_at=schema.published_at,
            missing_fields=schema.missing_publication_fields(),
        )

    def _interview_frequency_ordering(self) -> ColumnElement[int]:
        return case(
            (
                CompetencyMatrixItemModel.interview_frequency == InterviewFrequencyEnum.CONSTANTLY,
                0,
            ),
            (CompetencyMatrixItemModel.interview_frequency == InterviewFrequencyEnum.OFTEN, 1),
            (CompetencyMatrixItemModel.interview_frequency == InterviewFrequencyEnum.RARELY, 2),
            (
                CompetencyMatrixItemModel.interview_frequency == InterviewFrequencyEnum.NEVER_SEEN,
                3,
            ),
            else_=4,
        )

    def _ordered_interview_frequencies(
        self,
        *,
        values: list[InterviewFrequencyEnum],
    ) -> list[InterviewFrequencyEnum]:
        order = {
            InterviewFrequencyEnum.CONSTANTLY: 0,
            InterviewFrequencyEnum.OFTEN: 1,
            InterviewFrequencyEnum.RARELY: 2,
            InterviewFrequencyEnum.NEVER_SEEN: 3,
        }
        return sorted(values, key=lambda value: order[value])

    def _workspace_missing_condition(self) -> ColumnElement[bool]:
        return or_(
            *[condition for _field, condition in self._workspace_missing_field_conditions()],
        )

    def _workspace_missing_count(self) -> ColumnElement[int]:
        conditions = self._workspace_missing_field_conditions()
        count: ColumnElement[int] = case((conditions[0][1], 1), else_=0)
        for _field, condition in conditions[1:]:
            count += case((condition, 1), else_=0)
        return count

    def _workspace_missing_field_conditions(
        self,
    ) -> tuple[tuple[CompetencyMatrixMissingFieldEnum, ColumnElement[bool]], ...]:
        return (
            (
                CompetencyMatrixMissingFieldEnum.SLUG,
                self._blank_text_condition(CompetencyMatrixItemModel.slug),
            ),
            (CompetencyMatrixMissingFieldEnum.GRADE, CompetencyMatrixItemModel.grade.is_(None)),
            (
                CompetencyMatrixMissingFieldEnum.QUESTION_RU,
                self._blank_text_condition(CompetencyMatrixItemModel.question_ru),
            ),
            (
                CompetencyMatrixMissingFieldEnum.QUESTION_EN,
                self._blank_text_condition(CompetencyMatrixItemModel.question_en),
            ),
            (
                CompetencyMatrixMissingFieldEnum.ANSWER_RU,
                self._blank_text_condition(CompetencyMatrixItemModel.answer_ru),
            ),
            (
                CompetencyMatrixMissingFieldEnum.ANSWER_EN,
                self._blank_text_condition(CompetencyMatrixItemModel.answer_en),
            ),
            (
                CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_RU,
                self._blank_text_condition(
                    CompetencyMatrixItemModel.interview_answer_explanation_ru,
                ),
            ),
            (
                CompetencyMatrixMissingFieldEnum.INTERVIEW_ANSWER_EXPLANATION_EN,
                self._blank_text_condition(
                    CompetencyMatrixItemModel.interview_answer_explanation_en,
                ),
            ),
        )

    def _blank_text_condition(self, column: InstrumentedAttribute[str]) -> ColumnElement[bool]:
        return func.length(func.trim(column)) == 0

    def _ensure_first_published_at(self, *, item_model: CompetencyMatrixItemModel) -> None:
        if (
            item_model.publish_status == PublishStatusEnum.PUBLISHED
            and item_model.published_at is None
        ):
            item_model.published_at = datetime.now(tz=UTC)

    async def get_resources_by_ids(
        self,
        resource_ids: list[str],
    ) -> ExternalResources:
        ids = bindparam("ids", value=resource_ids, type_=ARRAY(String))
        cte = select(func.unnest(ids).label("resource_id")).cte("ids")
        stmt = select(ExternalResourceModel).join(
            cte,
            ExternalResourceModel.id == cte.c.resource_id,
        )
        resources = await self.session.scalars(stmt)
        return ExternalResources(values=[resource.to_domain_schema() for resource in resources])

    async def delete_competency_matrix_item(self, item_id: str) -> None:
        stmt = select(CompetencyMatrixItemModel).where(CompetencyMatrixItemModel.id == item_id)
        item = await self.session.scalar(stmt)
        if item is None:
            raise CompetencyMatrixItemNotFoundError
        await self.session.delete(item)
        await self.session.flush()

    async def search_competency_matrix_resources(
        self,
        search_name: str,
        limit: int,
        language: LanguageEnum,
    ) -> ExternalResources:
        lowered_search_name = search_name.lower()
        active_name_column = self._resource_name_column(language=language)
        secondary_name_column = self._secondary_resource_name_column(language=language)
        search_query = bindparam(
            "resource_search_query",
            value=lowered_search_name,
            type_=String(),
        )
        search_pattern = f"%{lowered_search_name}%"
        prefix_pattern = f"{lowered_search_name}%"
        active_name = func.lower(active_name_column)
        secondary_name = func.lower(secondary_name_column)
        url = func.lower(ExternalResourceModel.url)
        fuzzy_search_allowed = (
            len(lowered_search_name) >= constants.search.min_trigram_fuzzy_query_length
        )
        similarity_score = func.greatest(
            func.similarity(active_name, search_query),
            func.similarity(secondary_name, search_query),
            func.similarity(url, search_query),
            func.word_similarity(search_query, active_name),
            func.word_similarity(search_query, secondary_name),
            func.word_similarity(search_query, url),
        )
        substring_filters = (
            active_name.like(search_pattern),
            secondary_name.like(search_pattern),
            url.like(search_pattern),
        )
        if fuzzy_search_allowed:
            resource_id = ExternalResourceModel.id.label("resource_id")
            candidate_filters = (
                *substring_filters,
                active_name.op("%")(search_query),
                secondary_name.op("%")(search_query),
                url.op("%")(search_query),
                active_name.op("%>")(search_query),
                secondary_name.op("%>")(search_query),
                url.op("%>")(search_query),
            )
            candidates = union(
                *(
                    select(resource_id).where(candidate_filter)
                    for candidate_filter in candidate_filters
                ),
            ).cte("resource_search_candidates")
            stmt = select(ExternalResourceModel).join(
                candidates,
                candidates.c.resource_id == ExternalResourceModel.id,
            )
        else:
            stmt = select(ExternalResourceModel).where(or_(*substring_filters))
        stmt = stmt.order_by(
            case(
                (active_name == lowered_search_name, 0),
                (active_name.like(prefix_pattern), 1),
                (secondary_name == lowered_search_name, 2),
                (secondary_name.like(prefix_pattern), 3),
                (url.like(search_pattern), 4),
                else_=5,
            ),
            similarity_score.desc(),
            active_name,
            ExternalResourceModel.id,
        ).limit(limit)
        resources = await self.session.scalars(stmt)
        return ExternalResources(values=[resource.to_domain_schema() for resource in resources])

    async def list_queued_questions(self) -> QueuedCompetencyMatrixQuestions:
        stmt = (
            select(QueuedQuestionModel)
            .options(*self._queued_question_domain_load_options())
            .order_by(
                QueuedQuestionModel.created_at,
                QueuedQuestionModel.id,
            )
        )
        questions = await self.session.scalars(stmt)
        return QueuedCompetencyMatrixQuestions(
            values=[question.to_domain_schema(claim=None) for question in questions],
        )

    async def list_queued_questions_with_active_claims(
        self,
        *,
        active_at: datetime,
    ) -> QueuedCompetencyMatrixQuestions:
        stmt = (
            select(QueuedQuestionModel, MatrixQuestionClaimModel, AgentClientModel.name)
            .outerjoin(
                MatrixQuestionClaimModel,
                and_(
                    MatrixQuestionClaimModel.queue_item_id == QueuedQuestionModel.id,
                    MatrixQuestionClaimModel.expires_at > active_at,
                ),
            )
            .outerjoin(
                AgentClientModel,
                AgentClientModel.id == MatrixQuestionClaimModel.agent_client_id,
            )
            .options(*self._queued_question_domain_load_options())
            .order_by(QueuedQuestionModel.created_at, QueuedQuestionModel.id)
        )
        rows = await self.session.execute(stmt)
        return QueuedCompetencyMatrixQuestions(
            values=[
                question.to_domain_schema(
                    claim=(
                        claim.to_summary(agent_client_name=cast("str", agent_client_name))
                        if claim is not None
                        else None
                    ),
                )
                for question, claim, agent_client_name in rows
            ],
        )

    async def get_queued_question(
        self,
        question_id: str,
        *,
        lock: bool,
    ) -> QueuedCompetencyMatrixQuestion:
        if lock:
            locked_question_id = await self.session.scalar(
                select(QueuedQuestionModel.id)
                .where(QueuedQuestionModel.id == question_id)
                .with_for_update(of=QueuedQuestionModel),
            )
            if locked_question_id is None:
                raise QueuedCompetencyMatrixQuestionNotFoundError
        stmt = (
            select(QueuedQuestionModel, MatrixQuestionClaimModel, AgentClientModel.name)
            .outerjoin(
                MatrixQuestionClaimModel,
                MatrixQuestionClaimModel.queue_item_id == QueuedQuestionModel.id,
            )
            .outerjoin(
                AgentClientModel,
                AgentClientModel.id == MatrixQuestionClaimModel.agent_client_id,
            )
            .where(QueuedQuestionModel.id == question_id)
            .options(*self._queued_question_domain_load_options())
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            raise QueuedCompetencyMatrixQuestionNotFoundError
        question, claim, agent_client_name = row
        return cast(
            "QueuedCompetencyMatrixQuestion",
            question.to_domain_schema(
                claim=(
                    claim.to_summary(agent_client_name=cast("str", agent_client_name))
                    if claim is not None
                    else None
                ),
            ),
        )

    async def question_suggestion_exists(
        self,
        *,
        fingerprint: CompetencyMatrixQuestionFingerprint,
        sheet_key: str,
    ) -> bool:
        fingerprint_digest = fingerprint.digest
        queued_question_exists = (
            select(QueuedQuestionModel.id)
            .where(
                QueuedQuestionModel.question_fingerprint == fingerprint_digest,
                QueuedQuestionModel.sheet == sheet_key,
            )
            .exists()
        )
        matrix_question_exists = (
            select(CompetencyMatrixItemModel.id)
            .join(CompetencyMatrixItemModel.subsection)
            .join(CompetencyMatrixSubsectionModel.section)
            .join(CompetencyMatrixSectionModel.sheet)
            .where(
                CompetencyMatrixSheetModel.key == sheet_key,
                or_(
                    CompetencyMatrixItemModel.question_ru_fingerprint == fingerprint_digest,
                    CompetencyMatrixItemModel.question_en_fingerprint == fingerprint_digest,
                ),
            )
            .exists()
        )
        return bool(
            await self.session.scalar(
                select(queued_question_exists | matrix_question_exists),
            ),
        )

    async def create_queued_question(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionCreateParams,
        suggested_by_username: str,
    ) -> QueuedCompetencyMatrixQuestion:
        question = QueuedQuestionModel.from_create_params(
            params=params,
            created_at=datetime.now(tz=UTC),
            suggested_by_username=suggested_by_username,
        )
        self.session.add(question)
        await self.session.flush()
        return question.to_domain_schema(claim=None)

    async def create_queued_questions(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionsCreateParams,
        suggested_by_username: str,
    ) -> QueuedCompetencyMatrixQuestions:
        created_at = datetime.now(tz=UTC)
        questions = [
            QueuedQuestionModel.from_create_params(
                params=question,
                created_at=created_at,
                suggested_by_username=suggested_by_username,
            )
            for question in params.questions
        ]
        self.session.add_all(questions)
        await self.session.flush()
        return QueuedCompetencyMatrixQuestions(
            values=[question.to_domain_schema(claim=None) for question in questions],
        )

    async def delete_queued_question(self, question_id: str) -> None:
        question = await self._get_queued_question_model(question_id=question_id)
        await self.session.delete(question)
        await self.session.flush()

    async def delete_question_claim(self, claim_id: str) -> None:
        await self.session.execute(
            delete(MatrixQuestionClaimModel).where(MatrixQuestionClaimModel.id == claim_id),
        )
        await self.session.flush()

    async def _get_queued_question_model(self, question_id: str) -> QueuedQuestionModel:
        stmt = (
            select(QueuedQuestionModel)
            .where(QueuedQuestionModel.id == question_id)
            .options(*self._queued_question_domain_load_options())
        )
        question = await self.session.scalar(stmt)
        if question is None:
            raise QueuedCompetencyMatrixQuestionNotFoundError
        return question

    def _queued_question_domain_load_options(self) -> tuple[Any, ...]:
        return (defer(QueuedQuestionModel.question_fingerprint),)

    def _resource_name_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ExternalResourceModel.name_ru
        return ExternalResourceModel.name_en

    def _secondary_resource_name_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ExternalResourceModel.name_en
        return ExternalResourceModel.name_ru

    def _question_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return CompetencyMatrixItemModel.question_ru
        return CompetencyMatrixItemModel.question_en

    def _sheet_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return CompetencyMatrixSheetModel.name_ru
        return CompetencyMatrixSheetModel.name_en

    def _section_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return CompetencyMatrixSectionModel.name_ru
        return CompetencyMatrixSectionModel.name_en

    def _subsection_column(
        self,
        *,
        language: LanguageEnum,
    ) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return CompetencyMatrixSubsectionModel.name_ru
        return CompetencyMatrixSubsectionModel.name_en

    def _date_start(self, *, value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    def _date_end(self, *, value: date) -> datetime:
        return datetime.combine(value, time.max, tzinfo=UTC)
