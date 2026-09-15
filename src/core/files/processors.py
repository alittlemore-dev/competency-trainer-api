from abc import ABC, abstractmethod

from core.files.schemas import FileUploadParams


class FileContentProcessor(ABC):
    @abstractmethod
    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        raise NotImplementedError
