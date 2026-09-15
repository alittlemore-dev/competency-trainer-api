from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import codes

from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.exceptions import AgentClientNameConflictError
from core.agent_access.schemas import (
    AgentAuditCursor,
    AgentAuditEvent,
    AgentAuditEventPage,
    AgentAuditEventPageParams,
    AgentAuditPolicy,
    AgentCertificate,
    AgentCertificatePolicy,
    AgentClient,
    AgentClientDetails,
    AgentClientRegisterParams,
    AgentClientRegistrationResult,
    AgentClientRevokeParams,
)
from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from tests.test_cases import ApiTestCase

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
CLIENT_ID = "00000000000000000000000000000001"
CERTIFICATE_ID = "00000000000000000000000000000002"


class TestOwnerAgentClientsAPI(ApiTestCase):
    @pytest.fixture
    def jwt_admin(self) -> JwtUser:
        return JwtUser(username="owner", role=RoleEnum.OWNER)

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_agent_admin_use_case()
        self.client_schema = AgentClient(
            id=CLIENT_ID,
            name="desktop-codex",
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(AgentScopeEnum),
            created_at=NOW,
            revoked_at=None,
        )
        self.certificate = AgentCertificate(
            id=CERTIFICATE_ID,
            agent_client_id=CLIENT_ID,
            fingerprint_sha256="a" * 64,
            serial_number="01",
            certificate_pem="-----BEGIN CERTIFICATE-----\nissued\n-----END CERTIFICATE-----",
            valid_from=NOW,
            expires_at=NOW + timedelta(days=90),
            created_at=NOW,
            revoked_at=None,
        )

    def test_owner_lists_clients_and_certificate_expiry(self) -> None:
        self.use_case.list_client_details.return_value = [
            AgentClientDetails(client=self.client_schema, certificates=(self.certificate,)),
        ]

        response = self.api.get_admin_agent_clients()

        self.asserts.status(response=response, expected_status=codes.OK)
        body = response.json()["clients"][0]
        assert body["id"] == CLIENT_ID
        assert body["status"] == "active"
        assert body["certificates"][0]["expiresAt"] == (NOW + timedelta(days=90)).isoformat()

    def test_owner_registers_csr_without_private_key_input(self) -> None:
        self.use_case.register_client.return_value = AgentClientRegistrationResult(
            client=self.client_schema,
            certificate=self.certificate,
            certificate_chain_pem="-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----",
        )
        scopes = [scope.value for scope in AgentScopeEnum]

        response = self.api.post_admin_agent_client(
            data={
                "name": "desktop-codex",
                "scopes": scopes,
                "csrPem": (
                    "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"
                ),
            },
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        assert "privateKey" not in response.text
        assert response.json()["certificatePem"] == self.certificate.certificate_pem
        params = self.use_case.register_client.await_args.kwargs["params"]
        policy = self.use_case.register_client.await_args.kwargs["policy"]
        assert params == AgentClientRegisterParams(
            name="desktop-codex",
            scopes=frozenset(AgentScopeEnum),
            csr_pem="-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----",
            registered_at=params.registered_at,
        )
        assert isinstance(policy, AgentCertificatePolicy)

    def test_duplicate_client_name_returns_stable_conflict(self) -> None:
        self.use_case.register_client.side_effect = AgentClientNameConflictError

        response = self.api.post_admin_agent_client(
            data={
                "name": "DESKTOP-CODEX",
                "scopes": [scope.value for scope in AgentScopeEnum],
                "csrPem": "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n"
                "-----END CERTIFICATE REQUEST-----",
            },
        )

        self.asserts.error_message(
            response=response,
            expected_status=codes.CONFLICT,
            expected_message=AgentClientNameConflictError.message,
        )

    def test_owner_revokes_client_permanently(self) -> None:
        response = self.api.post_revoke_admin_agent_client(client_id=CLIENT_ID)

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        params = self.use_case.revoke_client.await_args.kwargs["params"]
        assert params == AgentClientRevokeParams(
            agent_client_id=CLIENT_ID,
            revoked_at=params.revoked_at,
        )

    def test_owner_reads_privacy_safe_audit(self) -> None:
        next_cursor = AgentAuditCursor(
            created_at=NOW - timedelta(minutes=1),
            event_id="00000000000000000000000000000007",
        )
        self.use_case.list_audit_events.return_value = AgentAuditEventPage(
            events=(
                AgentAuditEvent(
                    id="00000000000000000000000000000003",
                    agent_client_id=CLIENT_ID,
                    certificate_id=CERTIFICATE_ID,
                    action=AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
                    queue_item_id="00000000000000000000000000000004",
                    matrix_item_id="00000000000000000000000000000005",
                    request_id="00000000000000000000000000000006",
                    result=AgentAuditResultEnum.SUCCESS,
                    input_digest="b" * 64,
                    created_at=NOW,
                ),
            ),
            next_cursor=next_cursor,
        )

        response = self.api.get_admin_agent_client_audit(
            client_id=CLIENT_ID,
            page_size=50,
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert "prompt" not in response.text.casefold()
        assert "answer" not in response.text.casefold()
        assert response.json()["events"][0]["inputDigest"] == "b" * 64
        assert response.json()["events"][0]["action"] == "save_matrix_question_draft"
        assert response.json()["nextCursor"] == {
            "createdAt": next_cursor.created_at.isoformat(),
            "eventId": next_cursor.event_id,
        }
        call = self.use_case.list_audit_events.await_args
        assert call.kwargs["params"] == AgentAuditEventPageParams(
            agent_client_id=CLIENT_ID,
            page_size=50,
            cursor=None,
        )
        assert isinstance(call.kwargs["requested_at"], datetime)
        assert isinstance(call.kwargs["policy"], AgentAuditPolicy)

    def test_owner_reads_next_audit_page_from_cursor(self) -> None:
        self.use_case.list_audit_events.return_value = AgentAuditEventPage(
            events=(),
            next_cursor=None,
        )
        cursor_created_at = NOW - timedelta(minutes=1)
        cursor_event_id = "00000000000000000000000000000007"

        response = self.api.get_admin_agent_client_audit(
            client_id=CLIENT_ID,
            page_size=25,
            cursor_created_at=cursor_created_at.isoformat(),
            cursor_event_id=cursor_event_id,
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"events": [], "nextCursor": None}
        params = self.use_case.list_audit_events.await_args.kwargs["params"]
        assert params == AgentAuditEventPageParams(
            agent_client_id=CLIENT_ID,
            page_size=25,
            cursor=AgentAuditCursor(
                created_at=cursor_created_at,
                event_id=cursor_event_id,
            ),
        )

    def test_audit_page_size_is_required(self) -> None:
        response = self.api.get_admin_agent_client_audit(
            client_id=CLIENT_ID,
            page_size=None,
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.list_audit_events.assert_not_awaited()


class TestNonOwnerAgentClientsAPI(ApiTestCase):
    @pytest.fixture(params=[RoleEnum.ADMIN, RoleEnum.MODERATOR])
    def jwt_admin(self, request: pytest.FixtureRequest) -> JwtUser:
        role = request.param
        return JwtUser(username=role.value, role=role)

    def test_non_owner_cannot_list_clients(self) -> None:
        response = self.api.get_admin_agent_clients()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)


class TestAnonymousAgentClientsAPI(ApiTestCase):
    def test_anonymous_cannot_access_owner_agent_client_contour(self) -> None:
        response = self.no_auth_api.get_admin_agent_clients()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
