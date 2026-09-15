from unittest.mock import Mock

import pytest

from core.files.file_name_generators import TimestampFileNameGenerator


class TestTimestampFileNameGenerator:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.mock_generator = Mock(return_value="abc123")
        self.timestamp_generator = TimestampFileNameGenerator(
            random_suffix_length=4,
            random_generator=self.mock_generator,
        )

    @pytest.mark.parametrize(
        ("folder", "file_extension", "expected_prefix", "expected_extension"),
        [
            (None, "", "", ""),
            ("images", ".jpg", "images/", ".jpg"),
            ("/documents/", "pdf", "documents/", ".pdf"),
            ("/folder/subfolder/", "", "folder/subfolder/", ""),
        ],
    )
    def test_generate_file_name_from_timestamp_and_random_suffix(
        self,
        folder: str | None,
        file_extension: str,
        expected_prefix: str,
        expected_extension: str,
    ) -> None:
        file_name = self.timestamp_generator(folder=folder, file_extension=file_extension)

        if expected_prefix:
            assert file_name.startswith(expected_prefix)
        else:
            assert not file_name.startswith("/")

        assert file_name.endswith(expected_extension)
        file_name_without_path = file_name.removeprefix(expected_prefix)
        stem = (
            file_name_without_path.removesuffix(expected_extension)
            if expected_extension
            else file_name_without_path
        )
        timestamp, suffix = stem.split("_", maxsplit=1)
        assert timestamp.isdigit()
        assert suffix == "abc123"
        self.mock_generator.assert_called_once_with(4)

    def test_uses_configured_random_suffix_length(self) -> None:
        random_generator = Mock(return_value="abcdef")
        generator = TimestampFileNameGenerator(
            random_suffix_length=6,
            random_generator=random_generator,
        )

        file_name = generator(folder=None, file_extension="")

        assert file_name.endswith("_abcdef")
        random_generator.assert_called_once_with(6)
