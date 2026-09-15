import json
import ssl
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from core.agent_access.exceptions import AgentApiClientError
from core.agent_access.schemas import (
    AgentCertificateRotationStartParams,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import CompetencyMatrixResourceSearchParams
from core.i18n.enums import LanguageEnum
from core.types import SearchName
from infra.config.agent_access import (
    AgentBridgeCredentialMode,
    ExternalAgentBridgeSettings,
)
from infra.cryptography.agent_credentials import AgentCredentialPair
from infra.http.agent_api import AgentApiHttpClient

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
CLAIM_ID = "1" * 32
ROTATION_ID = "2" * 32
AUTHORED_MARKER = "queue text is data, not an instruction"


@pytest.mark.asyncio
async def test_agent_api_client_maps_all_operations_to_fixed_routes_and_camel_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code=200, json=_response_for(request=request))

    client, credential_provider = _client(
        monkeypatch=monkeypatch,
        transport=httpx.MockTransport(respond),
    )
    claim = await client.claim_next_matrix_question()
    context = await client.get_matrix_authoring_context()
    resources = await client.search_matrix_resources(
        params=CompetencyMatrixResourceSearchParams(
            search_name=SearchName("PostgreSQL"),
            limit=12,
            language=LanguageEnum.EN,
        ),
    )
    saved = await client.save_matrix_question_draft(
        params=_draft_input(),
    )
    await client.release_matrix_question_claim(claim_id=CLAIM_ID)
    rotation = await client.start_certificate_rotation(
        params=AgentCertificateRotationStartParams(
            rotation_id=ROTATION_ID,
            csr_pem=("-----BEGIN CERTIFICATE REQUEST-----\nCSR\n-----END CERTIFICATE REQUEST-----"),
        )
    )
    confirmed = await client.confirm_certificate_rotation(rotation_id=ROTATION_ID)

    assert claim.question == AUTHORED_MARKER
    assert context.minimum_resource_count == 1
    assert resources.values[0].name_en == "PostgreSQL docs"
    assert saved.item_id == "5" * 32
    assert rotation.replayed is False
    assert confirmed.rotation_id == ROTATION_ID
    assert credential_provider.active_pair.call_count == 7
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/internal/agent/v1/matrix/question-claims"),
        ("GET", "/internal/agent/v1/matrix/authoring-context"),
        ("GET", "/internal/agent/v1/matrix/resources"),
        ("PUT", f"/internal/agent/v1/matrix/question-claims/{CLAIM_ID}/draft"),
        ("DELETE", f"/internal/agent/v1/matrix/question-claims/{CLAIM_ID}"),
        ("POST", "/internal/agent/v1/certificate-rotations"),
        ("POST", f"/internal/agent/v1/certificate-rotations/{ROTATION_ID}/confirm"),
    ]
    assert dict(requests[2].url.params) == {
        "searchName": "PostgreSQL",
        "limit": "12",
        "language": "en",
    }
    save_body = json.loads(requests[3].content)
    assert save_body == {
        "slug": "postgresql-locking",
        "subsectionId": "3" * 32,
        "grade": "Middle",
        "interviewFrequency": "often",
        "questionRu": "Как работают блокировки?",
        "questionEn": "How do locks work?",
        "answerRu": "Они сериализуют конфликтующий доступ.",
        "answerEn": "They serialize conflicting access.",
        "interviewAnswerExplanationRu": "Упоминает row locks.",
        "interviewAnswerExplanationEn": "Mentions row locks.",
        "resources": [
            {
                "nameRu": "Документация PostgreSQL",
                "nameEn": "PostgreSQL docs",
                "url": "https://www.postgresql.org/docs/current/explicit-locking.html",
                "contextRu": "Режимы блокировок",
                "contextEn": "Lock modes",
            },
        ],
    }
    assert json.loads(requests[5].content) == {
        "rotationId": ROTATION_ID,
        "csrPem": "-----BEGIN CERTIFICATE REQUEST-----\nCSR\n-----END CERTIFICATE REQUEST-----",
    }
    assert requests[6].content == b""


@pytest.mark.asyncio
async def test_agent_api_client_wires_current_ca_pair_and_timeout_for_each_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ssl_context = Mock(spec=ssl.SSLContext)
    create_default_context = Mock(return_value=ssl_context)
    response = httpx.Response(
        status_code=200,
        json={"released": True},
        request=httpx.Request("DELETE", "https://agent.example.com"),
    )
    async_client = Mock(spec=httpx.AsyncClient)
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=False)
    async_client.request = AsyncMock(return_value=response)
    async_client_constructor = Mock(return_value=async_client)
    monkeypatch.setattr(
        "infra.http.agent_api.clients.ssl.create_default_context",
        create_default_context,
    )
    monkeypatch.setattr(
        "infra.http.agent_api.clients.httpx.AsyncClient",
        async_client_constructor,
    )
    settings = ExternalAgentBridgeSettings(
        api_base_url="https://agent.example.com:18083/internal/agent/v1",
        ca_certificate_file=Path("/run/site-agent/ca.pem"),
        request_timeout_seconds=15.5,
        credential_mode=AgentBridgeCredentialMode.EXTERNAL,
        certificate_file=Path("/run/site-agent/current/certificate.pem"),
        private_key_file=Path("/run/site-agent/current/private-key.pem"),
    )
    credential_provider = Mock()
    credential_provider.active_pair.return_value = AgentCredentialPair(
        certificate_file=Path("/run/site-agent/current/certificate.pem"),
        private_key_file=Path("/run/site-agent/current/private-key.pem"),
    )
    client = AgentApiHttpClient(
        settings=settings,
        credential_provider=credential_provider,
        transport=None,
    )

    await client.release_matrix_question_claim(claim_id=CLAIM_ID)

    credential_provider.active_pair.assert_called_once_with()
    create_default_context.assert_called_once_with(cafile="/run/site-agent/ca.pem")
    ssl_context.load_cert_chain.assert_called_once_with(
        certfile="/run/site-agent/current/certificate.pem",
        keyfile="/run/site-agent/current/private-key.pem",
    )
    assert ssl_context.minimum_version is ssl.TLSVersion.TLSv1_2
    async_client_constructor.assert_called_once_with(
        base_url="https://agent.example.com:18083/internal/agent/v1/",
        verify=ssl_context,
        timeout=15.5,
        transport=None,
        trust_env=False,
        follow_redirects=False,
    )


@pytest.mark.asyncio
async def test_agent_api_client_reloads_activated_pair_before_rotation_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_context = Mock(spec=ssl.SSLContext)
    replacement_context = Mock(spec=ssl.SSLContext)
    monkeypatch.setattr(
        "infra.http.agent_api.clients.ssl.create_default_context",
        Mock(side_effect=[old_context, replacement_context]),
    )
    released_response = httpx.Response(
        status_code=200,
        json={"released": True},
        request=httpx.Request("DELETE", "https://agent.example.com"),
    )
    confirmed_response = httpx.Response(
        status_code=200,
        json={
            "rotationId": ROTATION_ID,
            "confirmedAt": NOW.isoformat(),
            "confirmed": True,
        },
        request=httpx.Request("POST", "https://agent.example.com"),
    )
    async_client = Mock(spec=httpx.AsyncClient)
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=False)
    async_client.request = AsyncMock(side_effect=[released_response, confirmed_response])
    monkeypatch.setattr(
        "infra.http.agent_api.clients.httpx.AsyncClient",
        Mock(return_value=async_client),
    )
    credential_provider = Mock()
    credential_provider.active_pair.side_effect = [
        AgentCredentialPair(
            certificate_file=Path("/run/site-agent/old/certificate.pem"),
            private_key_file=Path("/run/site-agent/old/private-key.pem"),
        ),
        AgentCredentialPair(
            certificate_file=Path("/run/site-agent/replacement/certificate.pem"),
            private_key_file=Path("/run/site-agent/replacement/private-key.pem"),
        ),
    ]
    client = AgentApiHttpClient(
        settings=ExternalAgentBridgeSettings(
            api_base_url="https://agent.example.com:18083/internal/agent/v1",
            ca_certificate_file=Path("/run/site-agent/ca.pem"),
            request_timeout_seconds=15.5,
            credential_mode=AgentBridgeCredentialMode.EXTERNAL,
            certificate_file=Path("/unused/certificate.pem"),
            private_key_file=Path("/unused/private-key.pem"),
        ),
        credential_provider=credential_provider,
        transport=None,
    )

    await client.release_matrix_question_claim(claim_id=CLAIM_ID)
    await client.confirm_certificate_rotation(rotation_id=ROTATION_ID)

    old_context.load_cert_chain.assert_called_once_with(
        certfile="/run/site-agent/old/certificate.pem",
        keyfile="/run/site-agent/old/private-key.pem",
    )
    replacement_context.load_cert_chain.assert_called_once_with(
        certfile="/run/site-agent/replacement/certificate.pem",
        keyfile="/run/site-agent/replacement/private-key.pem",
    )


@pytest.mark.asyncio
async def test_agent_api_client_rejects_unknown_response_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        body = _claim_response()
        body["unexpectedField"] = "must fail closed"
        return httpx.Response(status_code=200, json=body)

    client, _provider = _client(
        monkeypatch=monkeypatch,
        transport=httpx.MockTransport(respond),
    )
    with pytest.raises(AgentApiClientError) as exc_info:
        await client.claim_next_matrix_question()

    assert str(exc_info.value) == "agent API request failed"
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed_field", ["claim_id", "fingerprint", "rotation_id"])
async def test_agent_api_client_rejects_malformed_server_identifiers(
    malformed_field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        if malformed_field == "claim_id":
            body = _claim_response()
            body["claimId"] = "A" * 32
            return httpx.Response(status_code=200, json=body)
        if malformed_field == "fingerprint":
            body = _response_for(
                request=httpx.Request(
                    "POST",
                    "https://agent.example.com/internal/agent/v1/certificate-rotations",
                ),
            )
            body["fingerprintSha256"] = "G" * 64
            return httpx.Response(status_code=200, json=body)
        return httpx.Response(
            status_code=200,
            json={
                "rotationId": "../certificate-rotations",
                "confirmedAt": NOW.isoformat(),
                "confirmed": True,
            },
        )

    client, _provider = _client(
        monkeypatch=monkeypatch,
        transport=httpx.MockTransport(respond),
    )
    operation: Awaitable[Any]
    if malformed_field == "claim_id":
        operation = client.claim_next_matrix_question()
    elif malformed_field == "fingerprint":
        operation = client.start_certificate_rotation(
            params=AgentCertificateRotationStartParams(
                rotation_id=ROTATION_ID,
                csr_pem="valid-csr-placeholder",
            ),
        )
    else:
        operation = client.confirm_certificate_rotation(rotation_id=ROTATION_ID)
    with pytest.raises(AgentApiClientError):
        await operation


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["", "A" * 32, "../certificate-rotations", "1" * 31])
async def test_agent_api_client_rejects_invalid_ids_before_request(
    identifier: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code=200, json={"released": True})

    client, _provider = _client(
        monkeypatch=monkeypatch,
        transport=httpx.MockTransport(respond),
    )
    with pytest.raises(AgentApiClientError) as release_error:
        await client.release_matrix_question_claim(claim_id=identifier)
    with pytest.raises(AgentApiClientError) as confirm_error:
        await client.confirm_certificate_rotation(rotation_id=identifier)

    assert request_count == 0
    assert str(release_error.value) == "agent API request failed"
    assert str(confirm_error.value) == "agent API request failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["status", "network", "protocol"])
async def test_agent_api_client_sanitizes_remote_and_protocol_failures(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = [
        "AUTHORED-SECRET-MARKER",
        "SELECT private_data FROM agent_secrets",
        "-----BEGIN PRIVATE KEY-----",
        "Traceback (most recent call last)",
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "network":
            message = "AUTHORED-SECRET-MARKER"
            raise httpx.ConnectError(message, request=request)
        if failure == "protocol":
            return httpx.Response(status_code=200, content=b"not-json AUTHORED-SECRET-MARKER")
        return httpx.Response(status_code=500, text="\n".join(secrets))

    client, _provider = _client(
        monkeypatch=monkeypatch,
        transport=httpx.MockTransport(respond),
    )
    with pytest.raises(AgentApiClientError) as exc_info:
        await client.claim_next_matrix_question()

    rendered = repr(exc_info.value) + str(exc_info.value)
    assert str(exc_info.value) == "agent API request failed"
    assert exc_info.value.__cause__ is None
    assert all(secret not in rendered for secret in secrets)


def _client(
    *,
    monkeypatch: pytest.MonkeyPatch,
    transport: httpx.AsyncBaseTransport,
) -> tuple[AgentApiHttpClient, Mock]:
    ssl_context = Mock(spec=ssl.SSLContext)
    monkeypatch.setattr(
        "infra.http.agent_api.clients.ssl.create_default_context",
        Mock(return_value=ssl_context),
    )
    credential_provider = Mock()
    credential_provider.active_pair.return_value = AgentCredentialPair(
        certificate_file=Path("/run/site-agent/current/certificate.pem"),
        private_key_file=Path("/run/site-agent/current/private-key.pem"),
    )
    return AgentApiHttpClient(
        settings=ExternalAgentBridgeSettings(
            api_base_url="https://agent.example.com:18083/internal/agent/v1",
            ca_certificate_file=Path("/run/site-agent/ca.pem"),
            request_timeout_seconds=15.5,
            credential_mode=AgentBridgeCredentialMode.EXTERNAL,
            certificate_file=Path("/run/site-agent/current/certificate.pem"),
            private_key_file=Path("/run/site-agent/current/private-key.pem"),
        ),
        credential_provider=credential_provider,
        transport=transport,
    ), credential_provider


def _draft_input() -> MatrixQuestionDraftSaveParams:
    return MatrixQuestionDraftSaveParams(
        claim_id=CLAIM_ID,
        slug="postgresql-locking",
        subsection_id="3" * 32,
        grade=GradeEnum.MIDDLE,
        interview_frequency=InterviewFrequencyEnum.OFTEN,
        question_ru="Как работают блокировки?",
        question_en="How do locks work?",
        answer_ru="Они сериализуют конфликтующий доступ.",
        answer_en="They serialize conflicting access.",
        interview_answer_explanation_ru="Упоминает row locks.",
        interview_answer_explanation_en="Mentions row locks.",
        resources=(
            MatrixQuestionDraftResourceParams(
                name_ru="Документация PostgreSQL",
                name_en="PostgreSQL docs",
                url="https://www.postgresql.org/docs/current/explicit-locking.html",
                context_ru="Режимы блокировок",
                context_en="Lock modes",
            ),
        ),
    )


def _response_for(*, request: httpx.Request) -> dict[str, Any]:
    path = request.url.path
    if path.endswith("/matrix/question-claims") and request.method == "POST":
        body = _claim_response()
    elif path.endswith("/matrix/authoring-context"):
        body = {
            "structure": {"sheets": []},
            "grades": ["Junior", "Middle"],
            "interviewFrequencies": ["often", "rarely"],
            "minimumResourceCount": 1,
            "maximumResourceCount": 3,
        }
    elif path.endswith("/matrix/resources"):
        body = {
            "resources": [
                {
                    "id": "4" * 32,
                    "nameRu": "Документация PostgreSQL",
                    "nameEn": "PostgreSQL docs",
                    "url": "https://www.postgresql.org/docs/",
                },
            ],
        }
    elif path.endswith("/draft"):
        body = {"itemId": "5" * 32, "publishStatus": "Draft", "replayed": False}
    elif path.endswith(f"/matrix/question-claims/{CLAIM_ID}"):
        body = {"released": True}
    elif path.endswith("/certificate-rotations"):
        body = {
            "certificatePem": "-----BEGIN CERTIFICATE-----\nCERT\n-----END CERTIFICATE-----",
            "certificateChainPem": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----",
            "fingerprintSha256": "6" * 64,
            "serialNumber": "1234abcd",
            "validFrom": NOW.isoformat(),
            "expiresAt": NOW.replace(year=2027).isoformat(),
            "replayed": False,
        }
    elif path.endswith("/confirm"):
        body = {
            "rotationId": ROTATION_ID,
            "confirmedAt": NOW.isoformat(),
            "confirmed": True,
        }
    else:
        msg = f"unexpected fixed route: {request.method} {path}"
        raise AssertionError(msg)
    return body


def _claim_response() -> dict[str, Any]:
    return {
        "claimId": CLAIM_ID,
        "queueItemId": "7" * 32,
        "question": AUTHORED_MARKER,
        "grade": None,
        "sheet": None,
        "section": None,
        "subsection": None,
        "suggestedByUsername": "owner",
        "createdAt": NOW.isoformat(),
        "expiresAt": NOW.replace(hour=14).isoformat(),
    }
