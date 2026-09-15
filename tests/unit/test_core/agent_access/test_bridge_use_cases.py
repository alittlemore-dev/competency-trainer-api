from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, call

import pytest

from core.agent_access.clients import AgentApiClient
from core.agent_access.exceptions import AgentCertificateRotationConfirmationError
from core.agent_access.schemas import (
    AgentCertificateRotationConfirmation,
    AgentCertificateRotationStartParams,
    AgentClientCertificateRotation,
    IssuedLocalAgentCredentialRotation,
    LocalAgentCredentialRotationPolicy,
    MatrixQuestionDraftSaveParams,
    PreparedLocalAgentCredentialRotation,
)
from core.agent_access.storages import LocalAgentCredentialRotationStorage
from core.agent_access.use_cases import AgentBridgeUseCase, AutomaticAgentCredentialRotationUseCase
from core.competency_matrix.schemas import CompetencyMatrixResourceSearchParams
from core.generators import HexUuidIdGenerator
from core.i18n.enums import LanguageEnum
from core.types import SearchName
from tests.test_cases import TestCase

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
ROTATION_ID = "1" * 32
PREVIOUS_VERSION_ID = "2" * 32
CSR_PEM = "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"


class TestAgentBridgeUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.client = Mock(spec=AgentApiClient)
        self.use_case = AgentBridgeUseCase(client=self.client)

    async def test_delegates_exactly_five_matrix_operations(self) -> None:
        claim = Mock(name="claim")
        context = Mock(name="context")
        resources = Mock(name="resources")
        save_result = Mock(name="save_result")
        search_params = CompetencyMatrixResourceSearchParams(
            search_name=SearchName("PostgreSQL"),
            limit=12,
            language=LanguageEnum.EN,
        )
        save_params = Mock(spec=MatrixQuestionDraftSaveParams)
        self.client.claim_next_matrix_question.return_value = claim
        self.client.get_matrix_authoring_context.return_value = context
        self.client.search_matrix_resources.return_value = resources
        self.client.save_matrix_question_draft.return_value = save_result
        self.client.release_matrix_question_claim.return_value = None

        assert await self.use_case.claim_next_matrix_question() is claim
        assert await self.use_case.get_matrix_authoring_context() is context
        assert await self.use_case.search_matrix_resources(params=search_params) is resources
        assert await self.use_case.save_matrix_question_draft(params=save_params) is save_result
        await self.use_case.release_matrix_question_claim(claim_id=ROTATION_ID)

        self.client.claim_next_matrix_question.assert_awaited_once_with()
        self.client.get_matrix_authoring_context.assert_awaited_once_with()
        self.client.search_matrix_resources.assert_awaited_once_with(params=search_params)
        self.client.save_matrix_question_draft.assert_awaited_once_with(params=save_params)
        self.client.release_matrix_question_claim.assert_awaited_once_with(claim_id=ROTATION_ID)
        self.client.start_certificate_rotation.assert_not_awaited()
        self.client.confirm_certificate_rotation.assert_not_awaited()


class TestAutomaticAgentCredentialRotationUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=LocalAgentCredentialRotationStorage)
        self.client = Mock(spec=AgentApiClient)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.return_value = ROTATION_ID
        self.policy = LocalAgentCredentialRotationPolicy(
            rotation_window_seconds=14 * 24 * 60 * 60,
        )
        self.use_case = AutomaticAgentCredentialRotationUseCase(
            storage=self.storage,
            client=self.client,
            id_generator=self.id_generator,
        )
        self.prepared = PreparedLocalAgentCredentialRotation(
            rotation_id=ROTATION_ID,
            previous_version_id=PREVIOUS_VERSION_ID,
            csr_pem=CSR_PEM,
        )
        self.response = AgentClientCertificateRotation(
            certificate_pem="certificate",
            certificate_chain_pem="chain",
            fingerprint_sha256="a" * 64,
            serial_number="ab12",
            valid_from=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(days=90),
            replayed=False,
        )
        self.issued = IssuedLocalAgentCredentialRotation(
            rotation_id=ROTATION_ID,
            previous_version_id=PREVIOUS_VERSION_ID,
            csr_pem=CSR_PEM,
            fingerprint_sha256=self.response.fingerprint_sha256,
            serial_number=self.response.serial_number,
            valid_from=self.response.valid_from,
            expires_at=self.response.expires_at,
        )
        self.confirmation = AgentCertificateRotationConfirmation(
            rotation_id=ROTATION_ID,
            confirmed_at=NOW,
        )

    async def test_not_due_returns_false_without_creating_rotation_state(self) -> None:
        self.storage.load_pending_rotation.return_value = None
        self.storage.get_active_certificate_expires_at.return_value = NOW + timedelta(days=15)

        assert (
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy) is False
        )

        self.storage.prepare_rotation.assert_not_called()
        self.id_generator.get_next.assert_not_called()
        self.client.start_certificate_rotation.assert_not_awaited()
        self.client.confirm_certificate_rotation.assert_not_awaited()

    async def test_fresh_due_rotation_prepares_before_network_and_completes_in_order(self) -> None:
        events: list[str] = []

        def prepare(*, rotation_id: str) -> PreparedLocalAgentCredentialRotation:
            events.append(f"prepare:{rotation_id}")
            return self.prepared

        def start(*, params: AgentCertificateRotationStartParams) -> AgentClientCertificateRotation:
            events.append(f"start:{params.rotation_id}")
            return self.response

        def persist(**_kwargs: object) -> IssuedLocalAgentCredentialRotation:
            events.append("persist")
            return self.issued

        def activate(*, rotation: IssuedLocalAgentCredentialRotation) -> None:
            events.append(f"activate:{rotation.rotation_id}")

        def confirm(*, rotation_id: str) -> AgentCertificateRotationConfirmation:
            events.append(f"confirm:{rotation_id}")
            return self.confirmation

        def complete(*, rotation: IssuedLocalAgentCredentialRotation) -> None:
            events.append(f"complete:{rotation.rotation_id}")

        self.storage.load_pending_rotation.return_value = None
        self.storage.get_active_certificate_expires_at.return_value = NOW + timedelta(days=14)
        self.storage.prepare_rotation.side_effect = prepare
        self.client.start_certificate_rotation.side_effect = start
        self.storage.persist_replacement.side_effect = persist
        self.storage.is_rotation_active.return_value = False
        self.storage.activate_rotation.side_effect = activate
        self.client.confirm_certificate_rotation.side_effect = confirm
        self.storage.complete_rotation.side_effect = complete

        assert (
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy) is True
        )

        assert events == [
            f"prepare:{ROTATION_ID}",
            f"start:{ROTATION_ID}",
            "persist",
            f"activate:{ROTATION_ID}",
            f"confirm:{ROTATION_ID}",
            f"complete:{ROTATION_ID}",
        ]
        self.client.start_certificate_rotation.assert_awaited_once_with(
            params=AgentCertificateRotationStartParams(
                rotation_id=ROTATION_ID,
                csr_pem=CSR_PEM,
            ),
        )
        self.storage.persist_replacement.assert_called_once_with(
            pending=self.prepared,
            response=self.response,
            current_datetime=NOW,
        )

    async def test_prepared_replay_after_lost_response_reuses_rotation_id_and_csr(self) -> None:
        self.storage.load_pending_rotation.return_value = self.prepared
        self.client.start_certificate_rotation.side_effect = [
            RuntimeError("lost response"),
            self.response,
        ]
        self.storage.persist_replacement.return_value = self.issued
        self.storage.is_rotation_active.return_value = True
        self.client.confirm_certificate_rotation.return_value = self.confirmation

        with pytest.raises(RuntimeError, match="lost response"):
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy)
        assert (
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy) is True
        )

        expected_start = call(
            params=AgentCertificateRotationStartParams(
                rotation_id=ROTATION_ID,
                csr_pem=CSR_PEM,
            ),
        )
        assert self.client.start_certificate_rotation.await_args_list == [
            expected_start,
            expected_start,
        ]
        self.storage.prepare_rotation.assert_not_called()
        self.id_generator.get_next.assert_not_called()
        self.storage.persist_replacement.assert_called_once_with(
            pending=self.prepared,
            response=self.response,
            current_datetime=NOW,
        )

    async def test_issued_pending_skips_start_and_activates_before_confirmation(self) -> None:
        events: list[str] = []

        def activate(*, rotation: IssuedLocalAgentCredentialRotation) -> None:
            del rotation
            events.append("activate")

        def confirm(*, rotation_id: str) -> AgentCertificateRotationConfirmation:
            del rotation_id
            events.append("confirm")
            return self.confirmation

        def complete(*, rotation: IssuedLocalAgentCredentialRotation) -> None:
            del rotation
            events.append("complete")

        self.storage.load_pending_rotation.return_value = self.issued
        self.storage.is_rotation_active.return_value = False
        self.storage.activate_rotation.side_effect = activate
        self.client.confirm_certificate_rotation.side_effect = confirm
        self.storage.complete_rotation.side_effect = complete

        assert (
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy) is True
        )

        assert events == ["activate", "confirm", "complete"]
        self.client.start_certificate_rotation.assert_not_awaited()
        self.storage.persist_replacement.assert_not_called()

    async def test_already_active_issued_rotation_does_not_activate_again(self) -> None:
        self.storage.load_pending_rotation.return_value = self.issued
        self.storage.is_rotation_active.return_value = True
        self.client.confirm_certificate_rotation.return_value = self.confirmation

        assert (
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy) is True
        )

        self.storage.activate_rotation.assert_not_called()
        self.storage.complete_rotation.assert_called_once_with(rotation=self.issued)

    async def test_confirmation_mismatch_preserves_pending_rotation(self) -> None:
        self.storage.load_pending_rotation.return_value = self.issued
        self.storage.is_rotation_active.return_value = True
        self.client.confirm_certificate_rotation.return_value = (
            AgentCertificateRotationConfirmation(
                rotation_id="3" * 32,
                confirmed_at=NOW,
            )
        )

        with pytest.raises(AgentCertificateRotationConfirmationError):
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy)

        self.storage.complete_rotation.assert_not_called()

    async def test_persistence_failure_keeps_prepared_state_and_stops_workflow(self) -> None:
        self.storage.load_pending_rotation.return_value = self.prepared
        self.client.start_certificate_rotation.return_value = self.response
        self.storage.persist_replacement.side_effect = RuntimeError("disk unavailable")

        with pytest.raises(RuntimeError, match="disk unavailable"):
            await self.use_case.rotate_if_needed(current_datetime=NOW, policy=self.policy)

        self.storage.activate_rotation.assert_not_called()
        self.client.confirm_certificate_rotation.assert_not_awaited()
        self.storage.complete_rotation.assert_not_called()


@pytest.mark.parametrize(
    ("policy", "prepared", "response"),
    [
        (
            {"rotation_window_seconds": 0},
            {
                "rotation_id": ROTATION_ID,
                "previous_version_id": ROTATION_ID,
                "csr_pem": CSR_PEM,
            },
            {
                "certificate_pem": "certificate",
                "certificate_chain_pem": "chain",
                "fingerprint_sha256": "a" * 64,
                "serial_number": "ab12",
                "valid_from": NOW,
                "expires_at": NOW,
                "replayed": False,
            },
        ),
    ],
)
def test_local_rotation_value_objects_reject_invalid_state(
    policy: dict[str, object],
    prepared: dict[str, object],
    response: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="local credential rotation window must be positive"):
        LocalAgentCredentialRotationPolicy(**policy)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="prepared local credential rotation is invalid"):
        PreparedLocalAgentCredentialRotation(**prepared)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="issued local certificate rotation is invalid"):
        AgentClientCertificateRotation(**response)  # type: ignore[arg-type]
