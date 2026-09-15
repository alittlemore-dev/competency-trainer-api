from collections.abc import Iterable

import pytest
from verbose_http_exceptions.exc.base import BaseVerboseHTTPException

from core.articles.exceptions import ArticleNotFoundError, TagNotFoundError
from core.auth.exceptions import ForbiddenError, UnauthorizedError, UserNotFoundError
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotFoundError,
    QuestionQueueImportInvalidError,
    QuestionSuggestionQuotaExceededError,
    QueuedCompetencyMatrixQuestionNotFoundError,
)
from core.contacts.exceptions import ContactMeRequestNotFoundError
from core.exceptions import EntryNotFoundError
from core.files.exceptions import (
    ContentTypeNotAllowedError,
    FileClientInternalError,
    InvalidFileDataError,
    NamespaceNotAllowedError,
)


def core_exception_classes() -> Iterable[type[Exception]]:
    return (
        EntryNotFoundError,
        UnauthorizedError,
        ForbiddenError,
        UserNotFoundError,
        CompetencyMatrixItemNotFoundError,
        QueuedCompetencyMatrixQuestionNotFoundError,
        QuestionSuggestionQuotaExceededError,
        QuestionQueueImportInvalidError,
        ContactMeRequestNotFoundError,
        InvalidFileDataError,
        ContentTypeNotAllowedError,
        NamespaceNotAllowedError,
        FileClientInternalError,
        ArticleNotFoundError,
        TagNotFoundError,
    )


@pytest.mark.parametrize("exception_class", core_exception_classes())
def test_core_exception_does_not_inherit_verbose_http_exception(
    exception_class: type[Exception],
) -> None:
    assert not issubclass(exception_class, BaseVerboseHTTPException)
