from abc import ABC, abstractmethod


class QuestionQueueImportExcelReader(ABC):
    @abstractmethod
    def read_rows(self, *, content: bytes) -> list[tuple[object, ...]]:
        raise NotImplementedError
