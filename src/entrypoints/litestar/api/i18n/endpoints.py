from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, get, status_codes

from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.i18n.catalog import get_i18n_messages, get_language_label
from entrypoints.litestar.api.i18n.schemas import (
    I18nBundleResponseSchema,
    LanguageResponseSchema,
    LanguagesResponseSchema,
)
from entrypoints.litestar.api.parameters import I18nLanguagePath
from entrypoints.litestar.response_cache import ResponseCacheDomain
from infra.config.constants import constants
from infra.config.settings import settings


class I18nApiController(Controller):
    path = "/i18n"
    tags = ["i18n"]

    @get(
        "/languages",
        description="Get the available interface language list.",
        name="i18n-languages-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.I18N.cache_key_builder,
    )
    async def list_languages(self) -> LanguagesResponseSchema:
        return LanguagesResponseSchema(
            default_language=settings.i18n.default_language,
            languages=[
                LanguageResponseSchema.from_language(
                    language=language,
                    label=get_language_label(language=language),
                )
                for language in LanguageEnum
            ],
        )

    @get(
        "/bundles/{language:str}",
        description="Get an interface i18n bundle.",
        name="i18n-bundle-detail-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.I18N.cache_key_builder,
    )
    async def get_bundle(self, language: I18nLanguagePath) -> I18nBundleResponseSchema:
        return I18nBundleResponseSchema(
            language=language,
            messages=dict(get_i18n_messages(language=language)),
        )


api_router = DishkaRouter("", route_handlers=[I18nApiController])
