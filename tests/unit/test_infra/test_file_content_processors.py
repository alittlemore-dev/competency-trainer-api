from dataclasses import dataclass, replace
from io import BytesIO
from typing import Any, cast

import pytest
from PIL import Image

from core.files.enums import FilePurpose
from core.files.exceptions import FileImageOptimizationError
from core.files.processors import FileContentProcessor
from core.files.schemas import FileUploadParams
from infra.files.processors import (
    ArticleContentImageContentProcessor,
    ArticleCoverImageContentProcessor,
    AttachmentContentProcessor,
    PillowImageProcessor,
    PurposeFileContentProcessor,
)
from tests.test_cases import TestCase


class TestFileContentProcessors(TestCase):
    def setup_method(self) -> None:
        image_processor = PillowImageProcessor()
        self.processor = PurposeFileContentProcessor(
            processors={
                FilePurpose.ARTICLE_COVER_IMAGE: ArticleCoverImageContentProcessor(
                    image_processor=image_processor,
                    max_width_px=160,
                    max_height_px=90,
                    webp_quality=82,
                    webp_method=6,
                    min_savings_ratio=0.10,
                ),
                FilePurpose.ARTICLE_CONTENT_IMAGE: ArticleContentImageContentProcessor(
                    image_processor=image_processor,
                    max_width_px=192,
                    max_height_px=192,
                    jpeg_webp_quality=88,
                    webp_method=6,
                    min_savings_ratio=0.10,
                ),
                FilePurpose.ATTACHMENT: AttachmentContentProcessor(),
            },
        )

    def test_process_dispatches_cover_policy_to_sixteen_nine_webp(self) -> None:
        original = create_rgb_png(width=640, height=480)

        result = self.processor.process(
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                name="Cover image",
                original_name="cover.png",
                mime_type="image/png",
                content=original,
            ),
        )

        assert result.mime_type == "image/webp"
        assert result.file_extension == ".webp"
        assert result.size_bytes <= int(len(original) * 0.90)
        with Image.open(BytesIO(result.content)) as image:
            assert image.format == "WEBP"
            assert image.width <= 160
            assert image.height <= 90

    def test_process_dispatches_content_policy_with_larger_square_bound(self) -> None:
        original = create_rgb_jpeg(width=640, height=480)

        result = self.processor.process(
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                name="Inline image",
                original_name="inline.jpg",
                mime_type="image/jpeg",
                content=original,
            ),
        )

        assert result.mime_type == "image/webp"
        with Image.open(BytesIO(result.content)) as image:
            assert image.format == "WEBP"
            assert image.width == 192
            assert image.height == 144

    def test_process_converts_content_png_to_lossless_webp_when_smaller(self) -> None:
        original = create_flat_png(width=64, height=64)

        result = self.processor.process(
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                name="Diagram",
                original_name="diagram.png",
                mime_type="image/png",
                content=original,
            ),
        )

        assert result.mime_type == "image/webp"
        assert result.size_bytes <= int(len(original) * 0.90)
        with Image.open(BytesIO(original)) as source, Image.open(BytesIO(result.content)) as output:
            assert output.format == "WEBP"
            assert output.convert("RGBA").tobytes() == source.convert("RGBA").tobytes()

    def test_process_keeps_tiny_content_webp_when_resize_is_not_needed(self) -> None:
        original = create_static_webp(width=4, height=4)
        params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            name="Tiny image",
            original_name="tiny.webp",
            mime_type="image/webp",
            content=original,
        )

        result = self.processor.process(params=params)

        assert result is params
        assert result.mime_type == "image/webp"
        assert result.content == original

    def test_process_validates_and_preserves_gif_without_conversion(self) -> None:
        original = create_gif()
        params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            name="Animation",
            original_name="animation.gif",
            mime_type="image/gif",
            content=original,
        )

        result = self.processor.process(params=params)

        assert result is params
        assert result.mime_type == "image/gif"
        assert result.content == original

    def test_process_preserves_animated_webp_frames_without_conversion(self) -> None:
        original = create_animated_webp()
        params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            name="Animated webp",
            original_name="animation.webp",
            mime_type="image/webp",
            content=original,
        )

        result = self.processor.process(params=params)

        assert result is params
        assert result.content == original
        with Image.open(BytesIO(result.content)) as image:
            animated_image = cast("Any", image)
            assert image.format == "WEBP"
            assert animated_image.is_animated
            assert animated_image.n_frames == 3

    @pytest.mark.parametrize(
        ("mime_type", "original_name"),
        [
            ("image/gif", "fake.gif"),
            ("image/webp", "fake.webp"),
        ],
    )
    def test_process_rejects_fake_article_image_bytes(
        self,
        mime_type: str,
        original_name: str,
    ) -> None:
        with pytest.raises(FileImageOptimizationError):
            self.processor.process(
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                    name="Broken image",
                    original_name=original_name,
                    mime_type=mime_type,
                    content=b"not an image",
                ),
            )

    def test_process_rejects_mime_spoofed_article_image_bytes(self) -> None:
        with pytest.raises(FileImageOptimizationError):
            self.processor.process(
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                    name="Spoofed image",
                    original_name="spoofed.gif",
                    mime_type="image/gif",
                    content=create_rgb_png(width=16, height=16),
                ),
            )

    def test_process_leaves_attachment_bytes_unchanged_without_image_validation(self) -> None:
        params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ATTACHMENT,
            name="Attachment",
            original_name="attachment.pdf",
            mime_type="application/pdf",
            content=b"%PDF fake but good enough for attachment tests",
        )

        result = self.processor.process(params=params)

        assert result is params
        assert result.content == params.content

    def test_purpose_processor_can_dispatch_to_non_image_processors(self) -> None:
        params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ATTACHMENT,
            name="Attachment",
            original_name="attachment.bin",
            mime_type="application/octet-stream",
            content=b"source",
        )
        processor = PurposeFileContentProcessor(
            processors={
                FilePurpose.ARTICLE_COVER_IMAGE: AttachmentContentProcessor(),
                FilePurpose.ARTICLE_CONTENT_IMAGE: AttachmentContentProcessor(),
                FilePurpose.ATTACHMENT: RecordingContentProcessor(result_content=b"processed"),
            },
        )

        result = processor.process(params=params)

        assert result.content == b"processed"


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordingContentProcessor(FileContentProcessor):
    result_content: bytes

    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        return replace(params, content=self.result_content)


def create_rgb_png(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel(
                (x, y),
                ((x * 13) % 256, (y * 17) % 256, ((x + y) * 19) % 256),
            )
    output = BytesIO()
    image.save(output, format="PNG", compress_level=0)
    return output.getvalue()


def create_rgb_jpeg(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel(
                (x, y),
                ((x * 7) % 256, (y * 11) % 256, ((x + y) * 5) % 256),
            )
    output = BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue()


def create_flat_png(*, width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (width, height), color=(20, 140, 210, 180)).save(
        output,
        format="PNG",
        compress_level=0,
    )
    return output.getvalue()


def create_gif() -> bytes:
    output = BytesIO()
    Image.new("P", (4, 4), color=1).save(output, format="GIF")
    return output.getvalue()


def create_static_webp(*, width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(
        output,
        format="WEBP",
        quality=80,
        method=6,
    )
    return output.getvalue()


def create_animated_webp() -> bytes:
    frames = [
        Image.new("RGB", (16, 16), color=(255, 0, 0)),
        Image.new("RGB", (16, 16), color=(0, 255, 0)),
        Image.new("RGB", (16, 16), color=(0, 0, 255)),
    ]
    output = BytesIO()
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    return output.getvalue()
