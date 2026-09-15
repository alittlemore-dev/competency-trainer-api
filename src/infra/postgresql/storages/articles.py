from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, TypeVar

from sqlalchemy import (
    Select,
    String,
    and_,
    bindparam,
    case,
    delete,
    func,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, joinedload, load_only, selectinload

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.exceptions import (
    ArticleFolderNotFoundError,
    ArticleNotFoundError,
    TagNotFoundError,
)
from core.articles.schemas import (
    Article,
    ArticleAnalyticsDailyStats,
    ArticleFilters,
    ArticleFolder,
    ArticleFolders,
    ArticlePublicStats,
    ArticlePublicStatsCollection,
    ArticleReactionCounts,
    ArticleTreeItemData,
    Tag,
    Tags,
)
from core.articles.storages import ArticleAnalyticsStorage, ArticlesStorage
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from infra.config.constants import constants
from infra.postgresql.models import (
    ArticleDailyAnalyticsModel,
    ArticleFileUsageModel,
    ArticleFolderModel,
    ArticleModel,
    ArticleReactionModel,
    ArticleToTagSecondaryModel,
    TagModel,
)

_SelectT = TypeVar("_SelectT")


@dataclass(kw_only=True)
class ArticlesDatabaseStorage(ArticlesStorage):
    session: AsyncSession

    async def get_article_by_slug(
        self,
        *,
        slug: str,
        lock: bool,
    ) -> Article:
        query = (
            select(ArticleModel)
            .where(ArticleModel.slug == slug)
            .options(
                joinedload(ArticleModel.folder),
                joinedload(ArticleModel.cover_image_file),
                selectinload(ArticleModel.file_usage_links),
                selectinload(ArticleModel.tag_links).selectinload(ArticleToTagSecondaryModel.tag),
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update(of=ArticleModel)
        article_model = await self.session.scalar(query)
        if article_model is None:
            raise ArticleNotFoundError
        return article_model.to_domain_schema(
            include_tags=True,
            include_files=True,
        )

    async def list_articles(self, *, filters: ArticleFilters) -> tuple[list[Article], int]:
        query = select(ArticleModel).options(joinedload(ArticleModel.folder))
        if filters.include_files:
            query = query.options(
                joinedload(ArticleModel.cover_image_file),
                selectinload(ArticleModel.file_usage_links),
            )
        if filters.include_tags:
            query = query.options(
                selectinload(ArticleModel.tag_links).selectinload(ArticleToTagSecondaryModel.tag),
            )
        query = self._apply_article_filters(query, filters=filters)
        query = query.order_by(*self._article_ordering(filters=filters))
        is_paginated = filters.page is not None and filters.page_size is not None
        if is_paginated:
            query = query.offset(filters.offset).limit(filters.limit)
            count_query = self._apply_article_filters(
                select(func.count(func.distinct(ArticleModel.id))),
                filters=filters,
            )
            total_count = (await self.session.scalar(count_query)) or 0
        elif filters.page is not None or filters.page_size is not None:
            raise ValueError

        article_models = await self.session.scalars(query)
        articles = [
            article_model.to_domain_schema(
                include_tags=filters.include_tags,
                include_files=filters.include_files,
            )
            for article_model in article_models.unique()
        ]

        return articles, total_count if is_paginated else len(articles)

    def _apply_article_filters(
        self,
        query: Select[tuple[_SelectT]],
        *,
        filters: ArticleFilters,
    ) -> Select[tuple[_SelectT]]:
        if filters.only_published is True:
            query = query.where(ArticleModel.publish_status == PublishStatusEnum.PUBLISHED)
        if filters.publish_status is not None:
            query = query.where(ArticleModel.publish_status == filters.publish_status)
        if filters.tag_slug is not None:
            query = (
                query.join(ArticleModel.tag_links)
                .join(ArticleToTagSecondaryModel.tag)
                .where(TagModel.slug == filters.tag_slug)
            )
        if filters.published_from is not None:
            query = query.where(
                ArticleModel.published_at >= self._date_start(value=filters.published_from),
            )
        if filters.published_to is not None:
            query = query.where(
                ArticleModel.published_at <= self._date_end(value=filters.published_to),
            )
        if filters.search_query is not None:
            query = query.where(
                self._search_vector(language=filters.language).op("@@")(
                    func.websearch_to_tsquery("simple", filters.search_query),
                ),
            )
        return query

    def _article_ordering(self, *, filters: ArticleFilters) -> tuple[Any, ...]:
        if filters.order_for_seo:
            return (
                ArticleModel.published_at.desc().nullslast(),
                ArticleModel.updated_at.desc(),
            )
        default_ordering = (
            case((ArticleModel.publish_status == PublishStatusEnum.PUBLISHED, 0), else_=1),
            ArticleModel.published_at.desc().nullslast(),
            ArticleModel.updated_at.desc(),
            self._title_column(language=filters.language),
        )
        if filters.search_query is None:
            return default_ordering
        return (
            func.ts_rank_cd(
                self._search_vector(language=filters.language),
                func.websearch_to_tsquery("simple", filters.search_query),
            ).desc(),
            *default_ordering,
        )

    def _search_vector(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ArticleModel.search_vector_ru
        return ArticleModel.search_vector_en

    def _title_column(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ArticleModel.title_ru
        return ArticleModel.title_en

    def _folder_name_column(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ArticleFolderModel.name_ru
        return ArticleFolderModel.name_en

    def _date_start(self, *, value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    def _date_end(self, *, value: date) -> datetime:
        return datetime.combine(value, time.max, tzinfo=UTC)

    async def list_tree_items(
        self,
        *,
        only_published: bool,
        language: LanguageEnum,
    ) -> list[ArticleTreeItemData]:
        if only_published:
            return await self._list_published_tree_items(language=language)

        filters = ArticleFilters(language=language)
        folder_column = self._folder_name_column(language=language).label("folder")
        title_column = self._title_column(language=language).label("title")
        query = (
            select(
                ArticleFolderModel.id.label("folder_id"),
                ArticleFolderModel.key.label("folder_key"),
                folder_column,
                title_column,
                ArticleModel.slug,
                ArticleModel.publish_status,
                ArticleModel.published_at,
                ArticleModel.updated_at,
            )
            .select_from(ArticleFolderModel)
            .join(
                ArticleModel,
                ArticleFolderModel.id == ArticleModel.folder_id,
            )
            .order_by(
                ArticleFolderModel.priority,
                ArticleFolderModel.id,
                *self._article_ordering(filters=filters),
            )
        )
        rows = await self.session.execute(query)
        return [
            ArticleTreeItemData(
                folder_id=row.folder_id,
                folder_key=row.folder_key,
                folder=row.folder,
                title=row.title,
                slug=row.slug,
                publish_status=row.publish_status,
                published_at=row.published_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def _list_published_tree_items(
        self,
        *,
        language: LanguageEnum,
    ) -> list[ArticleTreeItemData]:
        folder_column = self._folder_name_column(language=language).label("folder")
        title_column = self._title_column(language=language)
        article_rows = (
            select(
                title_column.label("title"),
                ArticleModel.slug.label("slug"),
                ArticleModel.publish_status.label("publish_status"),
                ArticleModel.published_at.label("published_at"),
                ArticleModel.updated_at.label("updated_at"),
            )
            .where(
                ArticleModel.folder_id == ArticleFolderModel.id,
                ArticleModel.publish_status == PublishStatusEnum.PUBLISHED,
            )
            .order_by(
                ArticleModel.published_at.desc().nullslast(),
                ArticleModel.updated_at.desc(),
                title_column,
            )
            .lateral("article_tree_articles")
        )
        query = (
            select(
                ArticleFolderModel.id.label("folder_id"),
                ArticleFolderModel.key.label("folder_key"),
                folder_column,
                article_rows.c.title,
                article_rows.c.slug,
                article_rows.c.publish_status,
                article_rows.c.published_at,
                article_rows.c.updated_at,
            )
            .select_from(ArticleFolderModel)
            .join(article_rows, true())
            .order_by(ArticleFolderModel.priority, ArticleFolderModel.id)
        )
        rows = await self.session.execute(query)
        return [
            ArticleTreeItemData(
                folder_id=row.folder_id,
                folder_key=row.folder_key,
                folder=row.folder,
                title=row.title,
                slug=row.slug,
                publish_status=row.publish_status,
                published_at=row.published_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def create_article(self, *, article: Article) -> Article:
        model = ArticleModel.from_domain_schema(article=article)
        model.tag_links = self._build_tag_links(article=article, existing_tag_links=[])
        self.session.add(model)
        await self.session.flush()
        return await self.get_article_by_slug(
            slug=article.slug,
            lock=False,
        )

    async def update_article(self, *, article: Article) -> Article:
        query = (
            select(ArticleModel)
            .where(ArticleModel.id == article.id)
            .options(
                selectinload(ArticleModel.tag_links),
                selectinload(ArticleModel.file_usage_links),
            )
        )
        model = await self.session.scalar(query)
        if model is None:
            raise ArticleNotFoundError
        previous_cover_image_file_id = model.cover_image_file_id
        model.update_from_domain_schema(article=article)
        if previous_cover_image_file_id != article.metadata.cover_image_file_id:
            self.session.expire(model, ["cover_image_file"])
        model.tag_links = self._build_tag_links(
            article=article,
            existing_tag_links=model.tag_links,
        )
        model.file_usage_links = self._build_file_usage_links(
            article=article,
            existing_file_usage_links=model.file_usage_links,
        )
        await self.session.flush()
        return await self.get_article_by_slug(
            slug=article.slug,
            lock=False,
        )

    def _build_tag_links(
        self,
        *,
        article: Article,
        existing_tag_links: list[ArticleToTagSecondaryModel],
    ) -> list[ArticleToTagSecondaryModel]:
        existing_tag_links_by_tag_id = {link.tag_id: link for link in existing_tag_links}
        return [
            existing_tag_links_by_tag_id[tag.id]
            if tag.id in existing_tag_links_by_tag_id
            else ArticleToTagSecondaryModel.from_domain_schema(tag=tag)
            for tag in article.tags
        ]

    def _build_file_usage_links(
        self,
        *,
        article: Article,
        existing_file_usage_links: list[ArticleFileUsageModel],
    ) -> list[ArticleFileUsageModel]:
        existing_links_by_key = {
            (link.file_id, link.usage): link for link in existing_file_usage_links
        }
        desired_links = ArticleFileUsageModel.from_domain_schema(article=article)
        return [
            existing_links_by_key.get((link.file_id, link.usage), link) for link in desired_links
        ]

    async def _get_article_model(self, *, slug: str, load_tag_links: bool) -> ArticleModel:
        query = select(ArticleModel).where(ArticleModel.slug == slug)
        if load_tag_links:
            query = query.options(selectinload(ArticleModel.tag_links))
        model = await self.session.scalar(query)
        if model is None:
            raise ArticleNotFoundError
        return model

    async def delete_article(self, *, slug: str) -> None:
        model = await self._get_article_model(slug=slug, load_tag_links=False)
        await self.session.delete(model)
        await self.session.flush()

    async def update_article_publish_status(
        self,
        *,
        slug: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        model = await self._get_article_model(slug=slug, load_tag_links=False)
        model.publish_status = publish_status
        if publish_status == PublishStatusEnum.PUBLISHED and model.published_at is None:
            model.published_at = datetime.now(tz=UTC)
        await self.session.flush()

    async def get_folder_by_id(self, *, folder_id: str) -> ArticleFolder:
        model = await self.session.get(ArticleFolderModel, folder_id)
        if model is None:
            raise ArticleFolderNotFoundError
        return model.to_domain_schema()

    async def list_folders(self, *, language: LanguageEnum) -> ArticleFolders:
        name_column = self._folder_name_column(language=language)
        models = await self.session.scalars(
            select(ArticleFolderModel).order_by(
                ArticleFolderModel.priority,
                func.lower(name_column),
                ArticleFolderModel.id,
            ),
        )
        return ArticleFolders(values=[model.to_domain_schema() for model in models])

    async def next_folder_priority(self) -> int:
        priority = await self.session.scalar(
            select(func.coalesce(func.max(ArticleFolderModel.priority), 0) + 1),
        )
        return int(priority or 1)

    async def folder_key_exists(self, *, key: str) -> bool:
        exists_stmt = select(
            select(ArticleFolderModel.id)
            .where(func.lower(ArticleFolderModel.key) == key.lower())
            .exists(),
        )
        return bool(await self.session.scalar(exists_stmt))

    async def create_folder(self, *, folder: ArticleFolder) -> ArticleFolder:
        model = ArticleFolderModel.from_domain_schema(folder=folder)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain_schema()

    async def update_folder_priorities(self, *, ordered_ids: tuple[str, ...]) -> None:
        if not ordered_ids:
            return
        priority_by_id = {
            ordered_id: priority for priority, ordered_id in enumerate(ordered_ids, start=1)
        }
        priority_cases = tuple(
            (ArticleFolderModel.id == folder_id, priority)
            for folder_id, priority in priority_by_id.items()
        )
        await self.session.execute(
            update(ArticleFolderModel)
            .where(ArticleFolderModel.id.in_(priority_by_id.keys()))
            .values(
                priority=case(
                    *priority_cases,
                    else_=ArticleFolderModel.priority,
                ),
            ),
        )
        await self.session.flush()

    async def get_tags_by_ids(
        self,
        *,
        tag_ids: list[str],
    ) -> Tags:
        if not tag_ids:
            return Tags(values=[])
        query = select(TagModel).where(TagModel.id.in_(tag_ids))
        models = await self.session.scalars(query)
        return Tags(values=[model.to_domain_schema() for model in models])

    async def list_tags(
        self,
        *,
        language: LanguageEnum,
        only_with_published_articles: bool,
    ) -> Tags:
        name_column = self._tag_name_column(language=language)
        query = select(TagModel).options(
            load_only(TagModel.id, TagModel.name_ru, TagModel.name_en, TagModel.slug),
        )
        if only_with_published_articles:
            query = query.where(
                select(ArticleToTagSecondaryModel.id)
                .join(
                    ArticleModel,
                    ArticleModel.id == ArticleToTagSecondaryModel.article_id,
                )
                .where(
                    ArticleToTagSecondaryModel.tag_id == TagModel.id,
                    ArticleModel.publish_status == PublishStatusEnum.PUBLISHED,
                )
                .exists(),
            )
        query = query.order_by(func.lower(name_column), TagModel.id)
        models = await self.session.scalars(query)
        return Tags(values=[model.to_domain_schema() for model in models])

    async def search_tags(
        self,
        *,
        search_name: str,
        limit: int,
        language: LanguageEnum,
    ) -> Tags:
        lowered_search_name = search_name.lower()
        active_name_column = self._tag_name_column(language=language)
        secondary_name_column = self._secondary_tag_name_column(language=language)
        search_query = bindparam(
            "tag_search_query",
            value=lowered_search_name,
            type_=String(),
        )
        search_pattern = f"%{lowered_search_name}%"
        prefix_pattern = f"{lowered_search_name}%"
        active_name = func.lower(active_name_column)
        secondary_name = func.lower(secondary_name_column)
        slug = func.lower(TagModel.slug)
        fuzzy_search_allowed = (
            func.length(search_query) >= constants.search.min_trigram_fuzzy_query_length
        )
        similarity_score = func.greatest(
            func.similarity(active_name, search_query),
            func.similarity(secondary_name, search_query),
            func.similarity(slug, search_query),
            func.word_similarity(search_query, active_name),
            func.word_similarity(search_query, secondary_name),
            func.word_similarity(search_query, slug),
        )
        query = (
            select(TagModel)
            .where(
                or_(
                    active_name.ilike(search_pattern),
                    secondary_name.ilike(search_pattern),
                    slug.ilike(search_pattern),
                    and_(
                        fuzzy_search_allowed,
                        or_(
                            active_name.op("%")(search_query),
                            secondary_name.op("%")(search_query),
                            slug.op("%")(search_query),
                            active_name.op("%>")(search_query),
                            secondary_name.op("%>")(search_query),
                            slug.op("%>")(search_query),
                        ),
                    ),
                ),
            )
            .order_by(
                case(
                    (active_name == lowered_search_name, 0),
                    (active_name.like(prefix_pattern), 1),
                    (secondary_name == lowered_search_name, 2),
                    (secondary_name.like(prefix_pattern), 3),
                    (slug.like(search_pattern), 4),
                    else_=5,
                ),
                similarity_score.desc(),
                active_name,
                TagModel.id,
            )
            .limit(limit)
        )
        models = await self.session.scalars(query)
        return Tags(values=[model.to_domain_schema() for model in models])

    def _tag_name_column(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return TagModel.name_ru
        return TagModel.name_en

    def _secondary_tag_name_column(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return TagModel.name_en
        return TagModel.name_ru

    async def create_tag(self, *, tag: Tag) -> Tag:
        model = TagModel.from_domain_schema(tag=tag)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain_schema()

    async def update_tag(self, *, tag: Tag) -> Tag:
        model = await self._get_tag_model(tag_id=tag.id)
        model.update_from_domain_schema(tag=tag)
        await self.session.flush()
        return model.to_domain_schema()

    async def _get_tag_model(self, *, tag_id: str) -> TagModel:
        model = await self.session.scalar(select(TagModel).where(TagModel.id == tag_id))
        if model is None:
            raise TagNotFoundError
        return model

    async def delete_tag(self, *, tag_id: str) -> None:
        deleted_tag_id = await self.session.scalar(
            delete(TagModel).where(TagModel.id == tag_id).returning(TagModel.id),
        )
        if deleted_tag_id is None:
            raise TagNotFoundError
        await self.session.flush()


@dataclass(kw_only=True)
class ArticleAnalyticsDatabaseStorage(ArticleAnalyticsStorage):
    session: AsyncSession

    async def increment_view(
        self,
        *,
        article_id: str,
        source_category: ArticleViewSourceCategory,
        viewed_on: date | None,
    ) -> None:
        await self._increment_daily_counter(
            article_id=article_id,
            source_category=source_category,
            viewed_on=viewed_on,
            view_count_increment=1,
            engaged_view_count_increment=0,
        )

    async def increment_engaged_view(
        self,
        *,
        article_id: str,
        source_category: ArticleViewSourceCategory,
        viewed_on: date | None,
    ) -> None:
        await self._increment_daily_counter(
            article_id=article_id,
            source_category=source_category,
            viewed_on=viewed_on,
            view_count_increment=0,
            engaged_view_count_increment=1,
        )

    async def _increment_daily_counter(
        self,
        *,
        article_id: str,
        source_category: ArticleViewSourceCategory,
        viewed_on: date | None,
        view_count_increment: int,
        engaged_view_count_increment: int,
    ) -> None:
        recorded_on = viewed_on if viewed_on is not None else datetime.now(tz=UTC).date()
        insert_statement = postgresql_insert(ArticleDailyAnalyticsModel).values(
            article_id=article_id,
            date=recorded_on,
            source_category=source_category,
            view_count=view_count_increment,
            engaged_view_count=engaged_view_count_increment,
        )
        await self.session.execute(
            insert_statement.on_conflict_do_update(
                index_elements=[
                    ArticleDailyAnalyticsModel.article_id,
                    ArticleDailyAnalyticsModel.date,
                    ArticleDailyAnalyticsModel.source_category,
                ],
                set_={
                    ArticleDailyAnalyticsModel.view_count.key: (
                        ArticleDailyAnalyticsModel.view_count + view_count_increment
                    ),
                    ArticleDailyAnalyticsModel.engaged_view_count.key: (
                        ArticleDailyAnalyticsModel.engaged_view_count + engaged_view_count_increment
                    ),
                },
            ),
        )
        await self.session.flush()

    async def get_public_stats(self, *, article_ids: list[str]) -> ArticlePublicStatsCollection:
        if not article_ids:
            return ArticlePublicStatsCollection(values=[])
        view_counts = await self._get_view_counts(article_ids=article_ids)
        reaction_counts = await self.get_reaction_counts(article_ids=article_ids)
        return ArticlePublicStatsCollection(
            values=[
                ArticlePublicStats(
                    article_id=article_id,
                    view_count=view_counts.get(article_id, 0),
                    reaction_counts=reaction_counts.get(article_id, ArticleReactionCounts.zero()),
                )
                for article_id in article_ids
            ],
        )

    async def _get_view_counts(self, *, article_ids: list[str]) -> dict[str, int]:
        result = await self.session.execute(
            select(
                ArticleDailyAnalyticsModel.article_id,
                func.coalesce(func.sum(ArticleDailyAnalyticsModel.view_count), 0),
            )
            .where(ArticleDailyAnalyticsModel.article_id.in_(article_ids))
            .group_by(ArticleDailyAnalyticsModel.article_id),
        )
        return {row[0]: row[1] for row in result}

    async def get_reaction_counts(
        self,
        *,
        article_ids: list[str],
    ) -> dict[str, ArticleReactionCounts]:
        if not article_ids:
            return {}
        result = await self.session.execute(
            select(
                ArticleReactionModel.article_id,
                ArticleReactionModel.reaction_kind,
                func.count(ArticleReactionModel.id),
            )
            .where(ArticleReactionModel.article_id.in_(article_ids))
            .group_by(ArticleReactionModel.article_id, ArticleReactionModel.reaction_kind),
        )
        raw_counts: dict[str, dict[ArticleReactionKind, int]] = {}
        for article_id, reaction_kind, count in result:
            raw_counts.setdefault(article_id, {})[self._to_reaction_kind(reaction_kind)] = count
        return {
            article_id: ArticleReactionCounts.from_counts(counts=counts)
            for article_id, counts in raw_counts.items()
        }

    async def set_reaction(
        self,
        *,
        article_id: str,
        article_scoped_voter_hash: str,
        reaction_kind: ArticleReactionKind | None,
    ) -> None:
        model = await self.session.scalar(
            select(ArticleReactionModel)
            .where(
                ArticleReactionModel.article_id == article_id,
                ArticleReactionModel.article_scoped_voter_hash == article_scoped_voter_hash,
            )
            .with_for_update(),
        )
        if reaction_kind is None:
            if model is not None:
                await self.session.delete(model)
            await self.session.flush()
            return
        if model is None:
            self.session.add(
                ArticleReactionModel(
                    article_id=article_id,
                    article_scoped_voter_hash=article_scoped_voter_hash,
                    reaction_kind=reaction_kind,
                ),
            )
        else:
            model.reaction_kind = reaction_kind
        await self.session.flush()

    async def get_daily_stats(
        self,
        *,
        date_from: date,
        date_to: date,
        language: LanguageEnum,
    ) -> list[ArticleAnalyticsDailyStats]:
        title_column = self._analytics_title_column(language=language)
        result = await self.session.execute(
            select(
                ArticleDailyAnalyticsModel.article_id,
                title_column,
                ArticleModel.slug,
                ArticleDailyAnalyticsModel.date,
                ArticleDailyAnalyticsModel.source_category,
                ArticleDailyAnalyticsModel.view_count,
                ArticleDailyAnalyticsModel.engaged_view_count,
            )
            .join(ArticleModel, ArticleModel.id == ArticleDailyAnalyticsModel.article_id)
            .where(
                ArticleDailyAnalyticsModel.date >= date_from,
                ArticleDailyAnalyticsModel.date <= date_to,
            )
            .order_by(
                ArticleDailyAnalyticsModel.date,
                title_column,
                ArticleDailyAnalyticsModel.source_category,
            ),
        )
        return [
            ArticleAnalyticsDailyStats(
                article_id=row[0],
                title=row[1],
                slug=row[2],
                date=row[3],
                source_category=self._to_source_category(row[4]),
                view_count=row[5],
                engaged_view_count=row[6],
            )
            for row in result
        ]

    def _analytics_title_column(self, *, language: LanguageEnum) -> InstrumentedAttribute[str]:
        if language == LanguageEnum.RU:
            return ArticleModel.title_ru
        return ArticleModel.title_en

    def _to_reaction_kind(self, value: ArticleReactionKind | str) -> ArticleReactionKind:
        if isinstance(value, ArticleReactionKind):
            return value
        try:
            return ArticleReactionKind.from_value(value)
        except ValueError:
            return ArticleReactionKind[value]

    def _to_source_category(
        self,
        value: ArticleViewSourceCategory | str,
    ) -> ArticleViewSourceCategory:
        if isinstance(value, ArticleViewSourceCategory):
            return value
        try:
            return ArticleViewSourceCategory.from_value(value)
        except ValueError:
            return ArticleViewSourceCategory[value]
