from pathlib import Path

import pytest
from pydantic import ValidationError

from infra.config.agent_access import (
    AgentBridgeCredentialMode,
    DesktopAgentBridgeSettings,
    ExternalAgentBridgeSettings,
    load_agent_bridge_settings,
)
from infra.config.constants import constants
from infra.config.settings import AgentAccessSettings


def set_agent_access_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "AGENT_ACCESS_ISSUING_CERTIFICATE_FILE": "/run/secrets/agent_issuing_certificate",
        "AGENT_ACCESS_ISSUING_PRIVATE_KEY_FILE": "/run/secrets/agent_issuing_private_key",
        "AGENT_ACCESS_CERTIFICATE_CHAIN_FILE": "/run/secrets/agent_certificate_chain",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def set_agent_bridge_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    credential_mode: str,
) -> None:
    values = {
        "SITE_AGENT_API_BASE_URL": "https://agent.example.com:18083/internal/agent/v1",
        "SITE_AGENT_CA_CERTIFICATE_FILE": "/opt/site-agent/ca.pem",
        "SITE_AGENT_CREDENTIAL_MODE": credential_mode,
        "SITE_AGENT_REQUEST_TIMEOUT_SECONDS": "15.5",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_agent_access_settings_require_every_production_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_access_environment(monkeypatch)
    monkeypatch.delenv("AGENT_ACCESS_CERTIFICATE_CHAIN_FILE")

    with pytest.raises(ValidationError):
        AgentAccessSettings(_env_file=None)


def test_agent_access_settings_reject_relative_secret_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_access_environment(monkeypatch)
    monkeypatch.setenv("AGENT_ACCESS_ISSUING_CERTIFICATE_FILE", "relative.pem")

    with pytest.raises(ValidationError):
        AgentAccessSettings(_env_file=None)


def test_agent_access_constants_match_security_policy() -> None:
    policy = constants.agent_access

    assert policy.claim_ttl_seconds == 7_200
    assert (policy.minimum_resource_count, policy.maximum_resource_count) == (1, 3)
    assert policy.certificate_lifetime_seconds == 90 * 24 * 60 * 60
    assert policy.certificate_rotation_window_seconds == 14 * 24 * 60 * 60
    assert policy.certificate_rotation_normal_access_overlap_seconds == 15 * 60
    assert policy.csr_pem_max_length == 16_384
    assert policy.request_body_max_size_bytes == 262_144
    assert policy.audit_page_max_size == 100
    assert policy.audit_retention_seconds == 365 * 24 * 60 * 60
    assert policy.trusted_client_certificate_header == "X-Agent-Client-Certificate"
    assert policy.desktop_directory_mode == 0o700
    assert policy.desktop_private_key_mode == 0o600
    assert policy.desktop_pending_file_mode == 0o600


@pytest.mark.parametrize(
    "base_url",
    [
        "http://agent.example.com/internal/agent/v1",
        "https://user:password@agent.example.com/internal/agent/v1",
        "https://agent.example.com/another/path",
        "https://agent.example.com/internal/agent/v1?token=secret",
    ],
)
def test_agent_bridge_settings_require_fixed_credential_free_https_url(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="desktop")
    monkeypatch.setenv("SITE_AGENT_API_BASE_URL", base_url)
    monkeypatch.setenv("SITE_AGENT_CREDENTIAL_DIRECTORY", "/opt/site-agent/credentials")

    with pytest.raises(ValidationError):
        load_agent_bridge_settings(env_file=None)


def test_desktop_agent_bridge_settings_require_absolute_credential_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="desktop")
    monkeypatch.setenv("SITE_AGENT_CREDENTIAL_DIRECTORY", "credentials")

    with pytest.raises(ValidationError):
        load_agent_bridge_settings(env_file=None)


def test_desktop_agent_bridge_settings_load_discriminated_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="desktop")
    monkeypatch.setenv("SITE_AGENT_CREDENTIAL_DIRECTORY", "/opt/site-agent/credentials")

    settings = load_agent_bridge_settings(env_file=None)

    assert isinstance(settings, DesktopAgentBridgeSettings)
    assert settings.credential_mode is AgentBridgeCredentialMode.DESKTOP
    assert settings.credential_directory == Path("/opt/site-agent/credentials")


def test_external_agent_bridge_settings_require_read_only_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="external")

    with pytest.raises(ValidationError):
        load_agent_bridge_settings(env_file=None)


def test_external_agent_bridge_settings_load_read_only_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="external")
    monkeypatch.setenv("SITE_AGENT_CERTIFICATE_FILE", "/run/secrets/agent_certificate")
    monkeypatch.setenv("SITE_AGENT_PRIVATE_KEY_FILE", "/run/secrets/agent_private_key")

    settings = load_agent_bridge_settings(env_file=None)

    assert isinstance(settings, ExternalAgentBridgeSettings)
    assert settings.credential_mode is AgentBridgeCredentialMode.EXTERNAL
    assert settings.certificate_file == Path("/run/secrets/agent_certificate")
    assert settings.private_key_file == Path("/run/secrets/agent_private_key")


def test_agent_bridge_settings_reject_unknown_credential_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="unsupported")

    with pytest.raises(ValidationError):
        load_agent_bridge_settings(env_file=None)


def test_agent_bridge_settings_require_positive_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_agent_bridge_environment(monkeypatch, credential_mode="desktop")
    monkeypatch.setenv("SITE_AGENT_CREDENTIAL_DIRECTORY", "/opt/site-agent/credentials")
    monkeypatch.setenv("SITE_AGENT_REQUEST_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        load_agent_bridge_settings(env_file=None)
