from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession
from valkey.asyncio import Valkey

from core.competency_matrix.generators import ItemIdGenerator, ResourceIdGenerator
from core.competency_matrix.parsers import QuestionQueueImportParser
from core.competency_matrix.readers import QuestionQueueImportExcelReader
from core.competency_matrix.schemas import QuestionSuggestionLimiterConfig
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage, QuestionSuggestionQuotaStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from infra.config.constants import constants
from infra.config.settings import settings
from infra.openpyxl.readers import OpenpyxlQuestionQueueImportExcelReader
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from infra.valkey.storages import ValkeyQuestionSuggestionQuotaStorage


class CompetencyMatrixProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_item_id_generator(self) -> ItemIdGenerator:
        return ItemIdGenerator()

    @provide(scope=Scope.APP)
    async def provide_resource_id_generator(self) -> ResourceIdGenerator:
        return ResourceIdGenerator()

    @provide(scope=Scope.APP)
    async def provide_question_queue_import_excel_reader(
        self,
    ) -> QuestionQueueImportExcelReader:
        return OpenpyxlQuestionQueueImportExcelReader()

    @provide(scope=Scope.APP)
    async def provide_question_queue_import_parser(
        self,
        excel_reader: QuestionQueueImportExcelReader,
    ) -> QuestionQueueImportParser:
        return QuestionQueueImportParser(
            rules=constants.question_queue_import.rules,
            excel_reader=excel_reader,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_competency_matrix_storage(
        self,
        session: AsyncSession,
    ) -> CompetencyMatrixStorage:
        return CompetencyMatrixDatabaseStorage(session=session)

    @provide(scope=Scope.APP)
    async def provide_question_suggestion_quota_storage(self) -> QuestionSuggestionQuotaStorage:
        return ValkeyQuestionSuggestionQuotaStorage(
            valkey=Valkey.from_url(
                settings.valkey.get_url(
                    db=constants.valkey.databases.question_suggestion_quota,
                ).get_secret_value(),
            ),
            namespace=constants.valkey.namespaces.matrix_question_suggestions,
        )

    @provide(scope=Scope.APP)
    async def provide_question_suggestion_limiter(
        self,
        quota_storage: QuestionSuggestionQuotaStorage,
    ) -> QuestionSuggestionLimiter:
        return QuestionSuggestionLimiter(
            quota_storage=quota_storage,
            config=QuestionSuggestionLimiterConfig(
                quota_secret=settings.app.secret_key.to_domain_secret(),
                anonymous_daily_limit=(
                    settings.competency_matrix.question_suggestion_anonymous_daily_limit
                ),
            ),
        )

    @provide(scope=Scope.REQUEST)
    async def provide_competency_matrix_use_case(
        self,
        storage: CompetencyMatrixStorage,
        question_suggestion_limiter: QuestionSuggestionLimiter,
    ) -> CompetencyMatrixUseCase:
        return CompetencyMatrixUseCase(
            storage=storage,
            question_suggestion_limiter=question_suggestion_limiter,
        )
