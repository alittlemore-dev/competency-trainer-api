from dataclasses import replace

import pytest
from litestar import Litestar
from litestar.routes import HTTPRoute
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from litestar.testing import TestClient

from core.agent_access.enums import AgentActionEnum, AgentAuditResultEnum, AgentScopeEnum
from core.agent_access.exceptions import (
    AgentAuthenticationError,
    AgentIdempotencyConflictError,
    AgentKnownAuthenticationError,
    MatrixQuestionClaimNotFoundError,
    MatrixQuestionDraftValidationError,
)
from core.agent_access.schemas import (
    AgentCertificate,
    AgentCertificatePolicy,
    AgentCertificateRotation,
    AgentCertificateRotationResult,
    AgentIdentity,
    MatrixAgentPolicy,
    MatrixAuthoringContext,
    MatrixQuestionClaim,
    MatrixQuestionDraftSaveResult,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    CompetencyMatrixStructure,
    QueuedCompetencyMatrixQuestion,
)
from infra.config.constants import constants
from tests.unit.test_api.agent_api.conftest import NOW, MockAgentApiProvider

PREFIX = "/internal/agent/v1"
EXPECTED_OPERATIONS = {
    ("POST", f"{PREFIX}/matrix/question-claims"),
    ("GET", f"{PREFIX}/matrix/authoring-context"),
    ("GET", f"{PREFIX}/matrix/resources"),
    ("PUT", f"{PREFIX}/matrix/question-claims/{{claim_id:str}}/draft"),
    ("DELETE", f"{PREFIX}/matrix/question-claims/{{claim_id:str}}"),
    ("POST", f"{PREFIX}/certificate-rotations"),
    ("POST", f"{PREFIX}/certificate-rotations/{{rotation_id:str}}/confirm"),
}


def test_main_app_mounts_exactly_seven_private_agent_operations(
    agent_api_app: Litestar,
) -> None:
    operations: set[tuple[str, str]] = set()
    for route in agent_api_app.routes:
        if not isinstance(route, HTTPRoute) or not route.path.startswith(PREFIX):
            continue
        operations.update(
            (method, route.path) for method in route.route_handler_map if method != "OPTIONS"
        )

    assert operations == EXPECTED_OPERATIONS


def test_private_app_exposes_exactly_seven_future_internal_operations(
    agent_api_app: Litestar,
) -> None:
    operations: set[tuple[str, str]] = set()
    route_handlers = []
    for route in agent_api_app.routes:
        if not isinstance(route, HTTPRoute) or not route.path.startswith(PREFIX):
            continue
        for method, (handler, _parameter_model) in route.route_handler_map.items():
            if method == "OPTIONS":
                continue
            operations.add((method, route.path))
            route_handlers.append(handler)

    assert operations == EXPECTED_OPERATIONS
    assert all(
        handler.opt["access_classification"] == "future internal" for handler in route_handlers
    )
    assert all(handler.opt["exclude_from_auth"] is True for handler in route_handlers)
    assert all(handler.cache is False for handler in route_handlers)
    assert {handler.opt["agent_action"] for handler in route_handlers} == set(AgentActionEnum)
    openapi_paths = agent_api_app.openapi_schema.to_schema()["paths"]
    assert all(not path.startswith(PREFIX) for path in openapi_paths)


def test_ordinary_main_route_bypasses_agent_authentication_and_audit(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
) -> None:
    response = agent_api_client.get("/api/i18n/languages")

    assert response.status_code == HTTP_200_OK
    agent_api_provider.identity_use_case.authenticate_business_client.assert_not_awaited()
    agent_api_provider.identity_use_case.authenticate_client.assert_not_awaited()
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_similar_internal_path_does_not_activate_agent_middleware(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
) -> None:
    response = agent_api_client.get("/internal/agent/v10/matrix/resources")

    assert response.status_code == HTTP_404_NOT_FOUND
    agent_api_provider.identity_use_case.authenticate_business_client.assert_not_awaited()
    agent_api_provider.identity_use_case.authenticate_client.assert_not_awaited()
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_agent_route_ignores_invalid_human_bearer_credentials(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_client.headers["Authorization"] = "Bearer invalid-human-token"
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = agent_identity

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_403_FORBIDDEN
    agent_api_provider.identity_use_case.authenticate_business_client.assert_awaited_once()


def test_private_app_rejects_docs_unknown_routes_and_wrong_methods(
    agent_api_client: TestClient,
) -> None:
    assert agent_api_client.get("/schema").status_code == HTTP_404_NOT_FOUND
    assert agent_api_client.get(f"{PREFIX}/matrix/question-claims").status_code == (
        HTTP_405_METHOD_NOT_ALLOWED
    )
    assert agent_api_client.post(f"{PREFIX}/arbitrary").status_code == HTTP_404_NOT_FOUND


@pytest.mark.parametrize("header", [None, "not-a-certificate", "%00"])
def test_missing_or_malformed_certificate_is_unauthorized_before_use_case(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    header: str | None,
) -> None:
    if header is None:
        del agent_api_client.headers["X-Agent-Client-Certificate"]
    else:
        agent_api_client.headers["X-Agent-Client-Certificate"] = header

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["code"] == "agent_authentication_failed"
    agent_api_provider.identity_use_case.authenticate_business_client.assert_not_awaited()
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_unknown_certificate_is_unauthorized_without_database_audit(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.side_effect = (
        AgentAuthenticationError()
    )

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_401_UNAUTHORIZED
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_known_expired_or_revoked_certificate_is_durably_rejected(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.side_effect = (
        AgentKnownAuthenticationError(
            agent_client_id="a" * 32,
            certificate_id="b" * 32,
        )
    )

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_401_UNAUTHORIZED
    audit = agent_api_provider.audit_use_case.record.await_args.kwargs["params"]
    assert audit.agent_client_id == "a" * 32
    assert audit.certificate_id == "b" * 32
    assert audit.action is AgentActionEnum.CLAIM_NEXT_MATRIX_QUESTION
    assert audit.result is AgentAuditResultEnum.REJECTED


def test_wrong_scope_is_forbidden_before_business_use_case_and_audited(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = agent_identity

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_403_FORBIDDEN
    agent_api_provider.matrix_use_case.claim_next_matrix_question.assert_not_awaited()
    audit = agent_api_provider.audit_use_case.record.await_args.kwargs["params"]
    assert audit.agent_client_id == agent_identity.agent_client_id
    assert audit.result is AgentAuditResultEnum.REJECTED


def test_claim_forwards_exact_matrix_policy_to_use_case(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    identity = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_QUEUE_CLAIM}),
    )
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = identity
    agent_api_provider.matrix_use_case.claim_next_matrix_question.return_value = (
        MatrixQuestionClaim(
            id="c" * 32,
            agent_client_id=identity.agent_client_id,
            question=QueuedCompetencyMatrixQuestion(
                id="d" * 32,
                question="What is PostgreSQL?",
                grade=GradeEnum.MIDDLE,
                sheet="Backend",
                section="Databases",
                subsection="PostgreSQL",
                suggested_by_username="owner",
                created_at=NOW,
                claim=None,
            ),
            claimed_at=NOW,
            expires_at=NOW,
        )
    )

    response = agent_api_client.post(f"{PREFIX}/matrix/question-claims")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "claimId": "c" * 32,
        "queueItemId": "d" * 32,
        "question": "What is PostgreSQL?",
        "grade": "Middle",
        "sheet": "Backend",
        "section": "Databases",
        "subsection": "PostgreSQL",
        "suggestedByUsername": "owner",
        "createdAt": NOW.isoformat().replace("+00:00", "Z"),
        "expiresAt": NOW.isoformat().replace("+00:00", "Z"),
    }
    assert (
        agent_api_provider.matrix_use_case.claim_next_matrix_question.await_args.kwargs["policy"]
        is agent_api_provider.matrix_policy
    )


def test_authoring_context_forwards_exact_matrix_policy_to_use_case(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    identity = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_CONTEXT_READ}),
    )
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = identity
    agent_api_provider.matrix_use_case.get_matrix_authoring_context.return_value = (
        MatrixAuthoringContext(
            structure=CompetencyMatrixStructure(sheets=[]),
            grades=(GradeEnum.MIDDLE,),
            interview_frequencies=(InterviewFrequencyEnum.OFTEN,),
            minimum_resource_count=1,
            maximum_resource_count=3,
        )
    )

    response = agent_api_client.get(f"{PREFIX}/matrix/authoring-context")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "structure": {"sheets": []},
        "grades": ["Middle"],
        "interviewFrequencies": ["often"],
        "minimumResourceCount": 1,
        "maximumResourceCount": 3,
    }
    assert (
        agent_api_provider.matrix_use_case.get_matrix_authoring_context.await_args.kwargs["policy"]
        is agent_api_provider.matrix_policy
    )


def test_save_schema_rejects_status_unknown_fields_and_authored_values_are_sanitized(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    marker = "AUTHORED-SECRET-MARKER"
    identity = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = identity
    payload = _valid_save_payload()
    payload["questionRu"] = marker
    payload["publishStatus"] = "Published"
    payload["publishedAt"] = NOW.isoformat()
    payload[marker] = marker

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=payload,
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    serialized = response.text
    assert marker not in serialized
    assert "Published" not in serialized
    assert response.json()["code"] == "validation_error"
    assert all(set(error) == {"location", "code"} for error in response.json()["errors"])
    agent_api_provider.matrix_use_case.save_matrix_question_draft.assert_not_awaited()


def test_save_schema_rejects_fourth_resource(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    payload = _valid_save_payload()
    resources = payload["resources"]
    assert isinstance(resources, list)
    payload["resources"] = resources * 4

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=payload,
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    agent_api_provider.matrix_use_case.save_matrix_question_draft.assert_not_awaited()


def test_save_schema_rejects_legacy_interview_answer_fields(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    payload = _valid_save_payload()
    legacy_parts = ("interview", "expected", "answer")
    legacy_field = legacy_parts[0] + "".join(part.title() for part in legacy_parts[1:])
    for language in ("Ru", "En"):
        current_field = f"interviewAnswerExplanation{language}"
        payload[f"{legacy_field}{language}"] = payload.pop(current_field)

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=payload,
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    agent_api_provider.matrix_use_case.save_matrix_question_draft.assert_not_awaited()


def test_save_maps_path_claim_id_and_never_accepts_publish_state(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    claim_id = "c" * 32
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    agent_api_provider.matrix_use_case.save_matrix_question_draft.return_value = (
        MatrixQuestionDraftSaveResult(item_id="d" * 32, replayed=False)
    )

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{claim_id}/draft",
        json=_valid_save_payload(),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "itemId": "d" * 32,
        "publishStatus": "Draft",
        "replayed": False,
    }
    params = agent_api_provider.matrix_use_case.save_matrix_question_draft.await_args.kwargs[
        "params"
    ]
    assert params.claim_id == claim_id
    assert isinstance(
        agent_api_provider.matrix_use_case.save_matrix_question_draft.await_args.kwargs["policy"],
        MatrixAgentPolicy,
    )
    assert not hasattr(params, "publish_status")
    assert not hasattr(params, "published_at")


def test_rotation_uses_client_authentication_and_client_generated_id(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    rotation_id = "c" * 32
    certificate = AgentCertificate(
        id="d" * 32,
        agent_client_id=agent_identity.agent_client_id,
        fingerprint_sha256="e" * 64,
        serial_number="02",
        certificate_pem="replacement certificate",
        valid_from=NOW,
        expires_at=NOW,
        created_at=NOW,
        revoked_at=None,
    )
    agent_api_provider.identity_use_case.authenticate_client.return_value = agent_identity
    agent_api_provider.rotation_use_case.rotate.return_value = AgentCertificateRotationResult(
        certificate=certificate,
        certificate_chain_pem="certificate chain",
        replayed=False,
    )

    response = agent_api_client.post(
        f"{PREFIX}/certificate-rotations",
        json={
            "rotationId": rotation_id,
            "csrPem": "certificate signing request",
        },
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["fingerprintSha256"] == "e" * 64
    assert response.json()["replayed"] is False
    agent_api_provider.identity_use_case.authenticate_business_client.assert_not_awaited()
    params = agent_api_provider.rotation_use_case.rotate.await_args.kwargs["params"]
    assert params.rotation_id == rotation_id
    assert params.csr_pem == "certificate signing request"
    assert params.rotated_at == NOW
    assert isinstance(
        agent_api_provider.rotation_use_case.rotate.await_args.kwargs["policy"],
        AgentCertificatePolicy,
    )
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_rotation_confirmation_uses_replacement_client_identity(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    rotation_id = "c" * 32
    replacement_identity = replace(agent_identity, certificate_id="d" * 32)
    agent_api_provider.identity_use_case.authenticate_client.return_value = replacement_identity
    agent_api_provider.rotation_use_case.confirm.return_value = AgentCertificateRotation(
        rotation_id=rotation_id,
        agent_client_id=agent_identity.agent_client_id,
        current_certificate_id=agent_identity.certificate_id,
        replacement_certificate_id=replacement_identity.certificate_id,
        csr_digest="e" * 64,
        created_at=NOW,
        normal_access_until=NOW,
        confirmed_at=NOW,
    )

    response = agent_api_client.post(
        f"{PREFIX}/certificate-rotations/{rotation_id}/confirm",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "rotationId": rotation_id,
        "confirmedAt": NOW.isoformat().replace("+00:00", "Z"),
        "confirmed": True,
    }
    identity = agent_api_provider.rotation_use_case.confirm.await_args.kwargs["identity"]
    params = agent_api_provider.rotation_use_case.confirm.await_args.kwargs["params"]
    assert identity == replacement_identity
    assert params.rotation_id == rotation_id
    assert params.confirmed_at == NOW
    agent_api_provider.identity_use_case.authenticate_business_client.assert_not_awaited()
    agent_api_provider.audit_use_case.record.assert_not_awaited()


def test_domain_conflict_has_stable_content_free_mapping_and_rejected_audit(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    agent_api_provider.matrix_use_case.save_matrix_question_draft.side_effect = (
        AgentIdempotencyConflictError()
    )

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=_valid_save_payload(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "agent_idempotency_conflict"
    assert agent_api_provider.audit_use_case.record.await_args.kwargs["params"].result is (
        AgentAuditResultEnum.REJECTED
    )


def test_domain_validation_has_stable_content_free_mapping_and_rejected_audit(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    agent_api_provider.matrix_use_case.save_matrix_question_draft.side_effect = (
        MatrixQuestionDraftValidationError()
    )

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=_valid_save_payload(),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["code"] == "invalid_request"
    assert agent_api_provider.audit_use_case.record.await_args.kwargs["params"].result is (
        AgentAuditResultEnum.REJECTED
    )


def test_domain_not_found_has_stable_content_free_mapping_and_rejected_audit(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_QUEUE_CLAIM}),
    )
    agent_api_provider.matrix_use_case.release_matrix_question_claim.side_effect = (
        MatrixQuestionClaimNotFoundError()
    )

    response = agent_api_client.delete(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["code"] == "not_found"
    assert agent_api_provider.audit_use_case.record.await_args.kwargs["params"].result is (
        AgentAuditResultEnum.REJECTED
    )


def test_unexpected_error_is_sanitized_and_failed_audit_is_independent(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    marker = "AUTHORED-SECRET-MARKER SELECT * FROM private"
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )
    agent_api_provider.matrix_use_case.save_matrix_question_draft.side_effect = RuntimeError(marker)

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        json=_valid_save_payload(),
    )

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"code": "internal_error", "requestId": "request-id"}
    assert marker not in response.text
    audit = agent_api_provider.audit_use_case.record.await_args.kwargs["params"]
    assert audit.result is AgentAuditResultEnum.FAILED
    assert marker not in repr(audit)


def test_request_body_limit_is_enforced_before_handler(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{'c' * 32}/draft",
        content=b"x" * (constants.agent_access.request_body_max_size_bytes + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE
    agent_api_provider.matrix_use_case.save_matrix_question_draft.assert_not_awaited()


def test_untrusted_path_and_inbound_request_id_never_reach_audit_metadata(
    agent_api_client: TestClient,
    agent_api_provider: MockAgentApiProvider,
    agent_identity: AgentIdentity,
) -> None:
    marker = "AUTHORED-SECRET-MARKER"
    agent_api_client.headers["X-Request-ID"] = marker
    agent_api_provider.identity_use_case.authenticate_business_client.return_value = replace(
        agent_identity,
        scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
    )

    response = agent_api_client.put(
        f"{PREFIX}/matrix/question-claims/{marker}/draft",
        json=_valid_save_payload(),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    audit = agent_api_provider.audit_use_case.record.await_args.kwargs["params"]
    assert audit.request_id == "request-id"
    assert marker not in repr(audit)
    assert marker not in response.text


def _valid_save_payload() -> dict[str, object]:
    return {
        "slug": "agent-authored-question",
        "subsectionId": "e" * 32,
        "grade": "Middle",
        "interviewFrequency": "often",
        "questionRu": "Вопрос",
        "questionEn": "Question",
        "answerRu": "Ответ",
        "answerEn": "Answer",
        "interviewAnswerExplanationRu": "Объяснение ответа",
        "interviewAnswerExplanationEn": "Answer explanation",
        "resources": [
            {
                "resourceId": "f" * 32,
                "contextRu": "Контекст",
                "contextEn": "Context",
            },
        ],
    }
