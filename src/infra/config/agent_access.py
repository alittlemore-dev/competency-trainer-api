from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    Field,
    PositiveFloat,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from infra.config.constants import constants


class AgentBridgeCredentialMode(StrEnum):
    DESKTOP = "desktop"
    EXTERNAL = "external"


class AgentBridgeBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=constants.path.env_file,
        env_prefix="SITE_AGENT_",
        extra="ignore",
    )

    api_base_url: str
    ca_certificate_file: Path
    request_timeout_seconds: PositiveFloat

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != constants.agent_access.api_path_prefix
            or parsed.query
            or parsed.fragment
        ):
            msg = "agent API base URL must be credential-free HTTPS with the fixed internal path"
            raise ValueError(msg)
        return value

    @field_validator("ca_certificate_file")
    @classmethod
    def validate_absolute_ca_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            msg = "agent bridge CA certificate path must be absolute"
            raise ValueError(msg)
        return value


class DesktopAgentBridgeSettings(AgentBridgeBaseSettings):
    credential_mode: Literal[AgentBridgeCredentialMode.DESKTOP]
    credential_directory: Path

    @field_validator("credential_directory")
    @classmethod
    def validate_absolute_credential_directory(cls, value: Path) -> Path:
        if not value.is_absolute():
            msg = "desktop agent bridge credential directory must be absolute"
            raise ValueError(msg)
        return value


class ExternalAgentBridgeSettings(AgentBridgeBaseSettings):
    credential_mode: Literal[AgentBridgeCredentialMode.EXTERNAL]
    certificate_file: Path
    private_key_file: Path

    @field_validator("certificate_file", "private_key_file")
    @classmethod
    def validate_absolute_credential_file_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            msg = "external agent bridge credential file paths must be absolute"
            raise ValueError(msg)
        return value


AgentBridgeSettings = Annotated[
    DesktopAgentBridgeSettings | ExternalAgentBridgeSettings,
    Field(discriminator="credential_mode"),
]


class AgentBridgeModeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=constants.path.env_file,
        env_prefix="SITE_AGENT_",
        extra="ignore",
    )

    credential_mode: AgentBridgeCredentialMode


def load_agent_bridge_settings(*, env_file: Path | None) -> AgentBridgeSettings:
    mode = AgentBridgeModeSettings(_env_file=env_file).credential_mode
    if mode is AgentBridgeCredentialMode.DESKTOP:
        return DesktopAgentBridgeSettings(_env_file=env_file)
    return ExternalAgentBridgeSettings(_env_file=env_file)
