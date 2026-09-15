from collections.abc import AsyncGenerator

import pytest_asyncio
from dishka import make_async_container
from litestar.testing import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.litestar.api.articles.schemas import (
    ArticleDetailResponseSchema,
    ArticleListResponseSchema,
    ArticleTreeResponseSchema,
)
from entrypoints.litestar.api.competency_matrix.schemas import (
    CompetencyMatrixSheetsListResponseSchema,
    PublicCompetencyMatrixItemDetailResponseSchema,
    PublicCompetencyMatrixItemsListResponseSchema,
)
from entrypoints.litestar.api.i18n.schemas import (
    I18nBundleResponseSchema,
    LanguagesResponseSchema,
)
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.ioc.registry import get_providers
from infra.postgresql.models import (
    ArticleFolderModel,
    ArticleModel,
    CompetencyMatrixItemModel,
    CompetencyMatrixSectionModel,
    CompetencyMatrixSheetModel,
    CompetencyMatrixSubsectionModel,
)
from tests.helpers.factory import FactoryHelper
from tests.helpers.storage import StorageHelper

ARTICLE_SLUG = "public-full-stack-article"
ARTICLE_FOLDER_ID = "00000000000000000000000000000065"
MATRIX_ITEM_SLUG = "public-full-stack-question"
MATRIX_SHEET_KEY = "public-full-stack"
MATRIX_STRUCTURE_ID = "00000000000000000000000000000065"


@pytest_asyncio.fixture
async def public_site_full_stack_client(
    session: AsyncSession,
) -> AsyncGenerator[TestClient]:
    factory = FactoryHelper()
    storage = StorageHelper(session=session)
    await storage.create_article(
        article=factory.core.article(
            slug=ARTICLE_SLUG,
            title_ru="Публичная full-stack статья",
            title_en="Public full-stack article",
            folder_id=ARTICLE_FOLDER_ID,
            folder_key="public-full-stack",
        ),
    )
    await storage.create_competency_matrix_item(
        item=factory.core.competency_matrix_item(
            item_id=101,
            slug=MATRIX_ITEM_SLUG,
            question_ru="Что проверяет full-stack тест?",
            question_en="What does the full-stack test verify?",
            sheet_id=MATRIX_STRUCTURE_ID,
            section_id=MATRIX_STRUCTURE_ID,
            subsection_id=MATRIX_STRUCTURE_ID,
            sheet_key=MATRIX_SHEET_KEY,
            sheet_ru="Публичный full-stack",
            sheet_en="Public full-stack",
        ),
    )
    await session.commit()

    container = make_async_container(*get_providers())
    app = create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[],
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        await container.close()
        await session.execute(
            delete(CompetencyMatrixItemModel).where(
                CompetencyMatrixItemModel.slug == MATRIX_ITEM_SLUG,
            ),
        )
        await session.execute(
            delete(CompetencyMatrixSubsectionModel).where(
                CompetencyMatrixSubsectionModel.id == MATRIX_STRUCTURE_ID,
            ),
        )
        await session.execute(
            delete(CompetencyMatrixSectionModel).where(
                CompetencyMatrixSectionModel.id == MATRIX_STRUCTURE_ID,
            ),
        )
        await session.execute(
            delete(CompetencyMatrixSheetModel).where(
                CompetencyMatrixSheetModel.id == MATRIX_STRUCTURE_ID,
            ),
        )
        await session.execute(delete(ArticleModel).where(ArticleModel.slug == ARTICLE_SLUG))
        await session.execute(
            delete(ArticleFolderModel).where(ArticleFolderModel.id == ARTICLE_FOLDER_ID),
        )
        await session.commit()


async def test_public_site_read_paths_use_real_http_wiring_and_postgresql(
    public_site_full_stack_client: TestClient,
) -> None:
    health_response = public_site_full_stack_client.get("/api/healthcheck")
    assert health_response.status_code == 200

    languages_response = public_site_full_stack_client.get("/api/i18n/languages")
    assert languages_response.status_code == 200
    languages = LanguagesResponseSchema.model_validate(languages_response.json())
    assert {language.code.value for language in languages.languages} == {"ru", "en"}

    bundle_response = public_site_full_stack_client.get("/api/i18n/bundles/ru")
    assert bundle_response.status_code == 200
    bundle = I18nBundleResponseSchema.model_validate(bundle_response.json())
    assert bundle.language.value == "ru"
    assert bundle.messages

    articles_response = public_site_full_stack_client.get(
        "/api/articles?page=1&pageSize=20&language=ru",
    )
    assert articles_response.status_code == 200
    articles = ArticleListResponseSchema.model_validate(articles_response.json())
    assert [article.slug for article in articles.articles] == [ARTICLE_SLUG]

    article_tree_response = public_site_full_stack_client.get("/api/articles/tree?language=ru")
    assert article_tree_response.status_code == 200
    article_tree = ArticleTreeResponseSchema.model_validate(article_tree_response.json())
    assert [article.slug for folder in article_tree.folders for article in folder.articles] == [
        ARTICLE_SLUG,
    ]

    article_detail_response = public_site_full_stack_client.get(
        f"/api/articles/detail/{ARTICLE_SLUG}?language=ru",
    )
    assert article_detail_response.status_code == 200
    article_detail = ArticleDetailResponseSchema.model_validate(article_detail_response.json())
    assert article_detail.slug == ARTICLE_SLUG
    assert article_detail.title == "Публичная full-stack статья"

    sheets_response = public_site_full_stack_client.get(
        "/api/competency-matrix/sheets?language=ru",
    )
    assert sheets_response.status_code == 200
    sheets = CompetencyMatrixSheetsListResponseSchema.model_validate(sheets_response.json())
    assert MATRIX_SHEET_KEY in {sheet.key for sheet in sheets.sheets}

    matrix_items_response = public_site_full_stack_client.get(
        f"/api/competency-matrix/items?sheetKey={MATRIX_SHEET_KEY}&language=ru",
    )
    assert matrix_items_response.status_code == 200
    matrix_items = PublicCompetencyMatrixItemsListResponseSchema.model_validate(
        matrix_items_response.json(),
    )
    item_slugs = [
        item.slug
        for section in matrix_items.sections
        for subsection in section.subsections
        for grade in subsection.grades
        for item in grade.items
    ]
    assert item_slugs == [MATRIX_ITEM_SLUG]

    matrix_detail_response = public_site_full_stack_client.get(
        f"/api/competency-matrix/items/public/{MATRIX_ITEM_SLUG}?language=ru",
    )
    assert matrix_detail_response.status_code == 200
    matrix_detail = PublicCompetencyMatrixItemDetailResponseSchema.model_validate(
        matrix_detail_response.json(),
    )
    assert matrix_detail.slug == MATRIX_ITEM_SLUG
    assert matrix_detail.question == "Что проверяет full-stack тест?"
