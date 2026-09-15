from collections.abc import Mapping
from dataclasses import dataclass, replace
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageOps

from core.files.enums import FilePurpose
from core.files.exceptions import FileImageOptimizationError
from core.files.processors import FileContentProcessor
from core.files.schemas import FileUploadParams

_MIME_TYPE_BY_IMAGE_FORMAT = {
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadedImage:
    image: Image.Image
    mime_type: str
    is_animated: bool


class ImageProcessor(Protocol):
    def load(self, *, params: FileUploadParams) -> LoadedImage: ...

    def resize_for_bounds(
        self,
        *,
        image: Image.Image,
        max_width_px: int,
        max_height_px: int,
    ) -> Image.Image: ...

    def is_oversized(
        self,
        *,
        image: Image.Image,
        max_width_px: int,
        max_height_px: int,
    ) -> bool: ...

    def encode_webp(self, *, image: Image.Image, quality: int, method: int) -> bytes: ...

    def encode_lossless_webp(self, *, image: Image.Image, method: int) -> bytes: ...


class ArticleImageProcessingSupport:
    @staticmethod
    def must_preserve_original(*, loaded: LoadedImage) -> bool:
        return loaded.mime_type == "image/gif" or (
            loaded.mime_type == "image/webp" and loaded.is_animated
        )

    @staticmethod
    def replace_if_worthwhile(
        *,
        params: FileUploadParams,
        optimized_content: bytes,
        min_savings_ratio: float,
    ) -> FileUploadParams:
        if len(optimized_content) > params.size_bytes * (1.0 - min_savings_ratio):
            return params
        return replace(
            params,
            mime_type="image/webp",
            content=optimized_content,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PurposeFileContentProcessor(FileContentProcessor):
    processors: Mapping[FilePurpose, FileContentProcessor]

    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        return self.processors[params.purpose].process(params=params)


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentContentProcessor(FileContentProcessor):
    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        return params


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleCoverImageContentProcessor(FileContentProcessor):
    image_processor: ImageProcessor
    max_width_px: int
    max_height_px: int
    webp_quality: int
    webp_method: int
    min_savings_ratio: float

    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        loaded = self.image_processor.load(params=params)
        if ArticleImageProcessingSupport.must_preserve_original(loaded=loaded):
            return params

        image = self.image_processor.resize_for_bounds(
            image=loaded.image,
            max_width_px=self.max_width_px,
            max_height_px=self.max_height_px,
        )
        optimized_content = self.image_processor.encode_webp(
            image=image,
            quality=self.webp_quality,
            method=self.webp_method,
        )
        return ArticleImageProcessingSupport.replace_if_worthwhile(
            params=params,
            optimized_content=optimized_content,
            min_savings_ratio=self.min_savings_ratio,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleContentImageContentProcessor(FileContentProcessor):
    image_processor: ImageProcessor
    max_width_px: int
    max_height_px: int
    jpeg_webp_quality: int
    webp_method: int
    min_savings_ratio: float

    def process(self, *, params: FileUploadParams) -> FileUploadParams:
        loaded = self.image_processor.load(params=params)
        if ArticleImageProcessingSupport.must_preserve_original(loaded=loaded):
            return params
        if loaded.mime_type == "image/webp" and not self.image_processor.is_oversized(
            image=loaded.image,
            max_width_px=self.max_width_px,
            max_height_px=self.max_height_px,
        ):
            return params

        image = self.image_processor.resize_for_bounds(
            image=loaded.image,
            max_width_px=self.max_width_px,
            max_height_px=self.max_height_px,
        )
        if loaded.mime_type == "image/png":
            optimized_content = self.image_processor.encode_lossless_webp(
                image=image,
                method=self.webp_method,
            )
        else:
            optimized_content = self.image_processor.encode_webp(
                image=image,
                quality=self.jpeg_webp_quality,
                method=self.webp_method,
            )
        return ArticleImageProcessingSupport.replace_if_worthwhile(
            params=params,
            optimized_content=optimized_content,
            min_savings_ratio=self.min_savings_ratio,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PillowImageProcessor:
    def load(self, *, params: FileUploadParams) -> LoadedImage:
        try:
            with Image.open(BytesIO(params.content)) as source_image:
                source_image.load()
                image_format = source_image.format
                mime_type = _MIME_TYPE_BY_IMAGE_FORMAT.get(image_format or "")
                if mime_type != params.mime_type:
                    raise FileImageOptimizationError
                image = ImageOps.exif_transpose(source_image).copy()
                return LoadedImage(
                    image=image,
                    mime_type=mime_type,
                    is_animated=bool(getattr(source_image, "is_animated", False)),
                )
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise FileImageOptimizationError from exc

    def resize_for_bounds(
        self,
        *,
        image: Image.Image,
        max_width_px: int,
        max_height_px: int,
    ) -> Image.Image:
        resized = ImageOps.exif_transpose(image).copy()
        resized.thumbnail((max_width_px, max_height_px), Image.Resampling.LANCZOS)
        return self._normalize_mode(image=resized)

    def is_oversized(
        self,
        *,
        image: Image.Image,
        max_width_px: int,
        max_height_px: int,
    ) -> bool:
        return image.width > max_width_px or image.height > max_height_px

    def encode_webp(self, *, image: Image.Image, quality: int, method: int) -> bytes:
        output = BytesIO()
        image.save(output, format="WEBP", quality=quality, method=method)
        return output.getvalue()

    def encode_lossless_webp(self, *, image: Image.Image, method: int) -> bytes:
        output = BytesIO()
        image.save(output, format="WEBP", lossless=True, method=method)
        return output.getvalue()

    @staticmethod
    def _normalize_mode(*, image: Image.Image) -> Image.Image:
        if image.mode in {"RGB", "RGBA"}:
            return image
        if image.mode in {"LA", "P"} or "transparency" in image.info:
            return image.convert("RGBA")
        return image.convert("RGB")
