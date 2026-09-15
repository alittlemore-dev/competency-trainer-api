import re
from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field, HttpUrl, TypeAdapter, ValidationError

from infra.config.constants import constants


def trim_required(value: str) -> str:
    trimmed_value = value.strip()
    if not trimmed_value:
        msg = "value must not be blank"
        raise ValueError(msg)
    return trimmed_value


def validate_slug(value: str) -> str:
    trimmed_value = trim_required(value)
    if re.fullmatch(constants.admin_validation.slug_pattern, trimmed_value) is None:
        msg = "value must be lowercase kebab-case"
        raise ValueError(msg)
    return trimmed_value


def validate_account_username(value: str) -> str:
    trimmed_value = trim_required(value)
    if re.fullmatch(constants.admin_validation.account_username_pattern, trimmed_value) is None:
        msg = "value must contain Latin letters, digits, dots, or underscores only"
        raise ValueError(msg)
    return trimmed_value


def validate_required_http_url(value: str) -> str:
    trimmed_value = trim_required(value)
    validate_http_url_format(trimmed_value)
    return trimmed_value


def validate_optional_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed_value = value.strip()
    if not trimmed_value:
        return None
    validate_http_url_format(trimmed_value)
    return trimmed_value


def validate_blankable_http_url(value: str) -> str:
    trimmed_value = value.strip()
    if not trimmed_value:
        return ""
    validate_http_url_format(trimmed_value)
    return trimmed_value


def validate_blankable_email(value: str) -> str:
    trimmed_value = value.strip()
    if not trimmed_value:
        return ""
    try:
        _email_adapter.validate_python(trimmed_value)
    except ValidationError as error:
        msg = "value must be a valid email address"
        raise ValueError(msg) from error
    return trimmed_value


def validate_optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed_value = value.strip()
    if not trimmed_value:
        msg = "value must not be blank"
        raise ValueError(msg)
    try:
        _email_adapter.validate_python(trimmed_value)
    except ValidationError as error:
        msg = "value must be a valid email address"
        raise ValueError(msg) from error
    return trimmed_value


def validate_http_url_format(value: str) -> None:
    try:
        _http_url_adapter.validate_python(value)
    except ValidationError as error:
        msg = "value must be a valid http or https URL"
        raise ValueError(msg) from error


_http_url_adapter = TypeAdapter(HttpUrl)
_email_adapter = TypeAdapter(EmailStr)

RequiredShortText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=constants.admin_validation.short_text_max_length,
    ),
    AfterValidator(trim_required),
]
SlugString = Annotated[
    str,
    Field(
        min_length=1,
        max_length=constants.admin_validation.short_text_max_length,
    ),
    AfterValidator(validate_slug),
]
AccountUsernameString = Annotated[
    str,
    Field(
        min_length=constants.admin_validation.account_username_min_length,
        max_length=constants.admin_validation.short_text_max_length,
    ),
    AfterValidator(validate_account_username),
]
AccountPasswordString = Annotated[
    str,
    Field(
        min_length=constants.admin_validation.account_password_min_length,
        max_length=constants.admin_validation.short_text_max_length,
    ),
]
ArticleContentText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=constants.admin_validation.article_content_max_length,
    ),
    AfterValidator(trim_required),
]
RequiredHttpUrlString = Annotated[
    str,
    Field(
        min_length=1,
        max_length=constants.admin_validation.url_max_length,
    ),
    AfterValidator(validate_required_http_url),
]
OptionalHttpUrlString = Annotated[
    str | None,
    Field(max_length=constants.admin_validation.url_max_length),
    AfterValidator(validate_optional_http_url),
]
BlankableHttpUrlString = Annotated[
    str,
    Field(max_length=constants.admin_validation.url_max_length),
    AfterValidator(validate_blankable_http_url),
]
BlankableEmailString = Annotated[
    str,
    Field(max_length=constants.admin_validation.email_max_length),
    AfterValidator(validate_blankable_email),
]
OptionalEmailString = Annotated[
    str | None,
    Field(
        min_length=1,
        max_length=constants.admin_validation.email_max_length,
    ),
    AfterValidator(validate_optional_email),
]
MatrixLongText = Annotated[
    str,
    Field(max_length=constants.admin_validation.matrix_long_text_max_length),
]
ShortText = Annotated[
    str,
    Field(max_length=constants.admin_validation.short_text_max_length),
]
