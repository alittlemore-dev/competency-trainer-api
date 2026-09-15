import uuid
from unittest.mock import Mock

import pytest

from core.files.file_name_generators import FileNameGenerator, UUIDFileNameGenerator


class TestUUIDFileNameGenerator:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.fixed_uuid = uuid.UUID("12345678-1234-5678-9abc-def012345678")
        self.mock_uuid_generator = Mock(return_value=self.fixed_uuid)
        self.uuid_generator = UUIDFileNameGenerator(generator=self.mock_uuid_generator)

    @pytest.mark.parametrize(
        ("folder", "file_extension", "expected"),
        [
            (None, "", "12345678123456789abcdef012345678"),
            ("images", ".jpg", "images/12345678123456789abcdef012345678.jpg"),
            ("/videos/", "mp4", "videos/12345678123456789abcdef012345678.mp4"),
            ("/folder/subfolder/", "", "folder/subfolder/12345678123456789abcdef012345678"),
        ],
    )
    def test_generate_file_name_from_uuid_hex(
        self,
        folder: str | None,
        file_extension: str,
        expected: str,
    ) -> None:
        file_name = self.uuid_generator(folder=folder, file_extension=file_extension)

        assert file_name == expected
        self.mock_uuid_generator.assert_called_once()


class TestNormalizeExtension:
    @pytest.mark.parametrize(
        ("file_extension", "expected"),
        [
            (".png", ".png"),
            ("jpg", ".jpg"),
            ("", ""),
            (".tar.gz", ".tar.gz"),
            ("tar.gz", ".tar.gz"),
        ],
    )
    def test_normalize_extension(self, file_extension: str, expected: str) -> None:
        assert FileNameGenerator.normalize_extension(file_extension) == expected
