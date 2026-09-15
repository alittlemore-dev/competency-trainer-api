from itertools import count
from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.competency_matrix.generators import ItemIdGenerator, ResourceIdGenerator
from core.competency_matrix.parsers import QuestionQueueImportParser
from core.competency_matrix.readers import QuestionQueueImportExcelReader
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from infra.config.constants import constants
from infra.openpyxl.readers import OpenpyxlQuestionQueueImportExcelReader

item_id_generator = count(1)
resource_id_generator = count(1)


class MockCompetencyMatrixProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_item_id_generator(self) -> ItemIdGenerator:
        mock = Mock(spec=ItemIdGenerator)
        mock.get_next = lambda: next(item_id_generator)
        return mock

    @provide(scope=Scope.APP)
    async def provide_resource_id_generator(self) -> ResourceIdGenerator:
        mock = Mock(spec=ResourceIdGenerator)
        mock.get_next = lambda: next(resource_id_generator)
        return mock

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

    @provide(scope=Scope.APP)
    async def provide_competency_matrix_use_case(self) -> CompetencyMatrixUseCase:
        return Mock(spec=CompetencyMatrixUseCase)
