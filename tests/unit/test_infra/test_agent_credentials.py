import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.agent_access.clients import AgentApiClient
from core.agent_access.exceptions import (
    AgentApiClientError,
    AgentCredentialCertificateValidationError,
    AgentCredentialStoreError,
)
from core.agent_access.schemas import (
    AgentCertificateRotationConfirmation,
    AgentCertificateRotationStartParams,
    AgentClientCertificateRotation,
    IssuedLocalAgentCredentialRotation,
    LocalAgentCredentialRotationPolicy,
)
from core.agent_access.storages import LocalAgentCredentialRotationStorage
from core.agent_access.use_cases import AutomaticAgentCredentialRotationUseCase
from core.generators import HexUuidIdGenerator
from infra.cryptography.agent_credentials import (
    DesktopAgentCredentialStore,
    ExternalAgentCredentialStore,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
INITIAL_ID = "1" * 32
ROTATION_ID = "2" * 32
LOCAL_ROTATION_POLICY = LocalAgentCredentialRotationPolicy(
    rotation_window_seconds=14 * 24 * 60 * 60,
)


@dataclass(slots=True)
class AgentApiRemoteStub:
    ca_key: ec.EllipticCurvePrivateKey
    ca_certificate: x509.Certificate
    output_mutator: Callable[[AgentClientCertificateRotation], AgentClientCertificateRotation]
    start_error_count: int
    confirm_error_count: int
    start_requests: list[AgentCertificateRotationStartParams]
    confirm_ids: list[str]
    before_start: Callable[[AgentCertificateRotationStartParams], None] | None
    response: AgentClientCertificateRotation | None = None

    async def start_certificate_rotation(
        self,
        *,
        params: AgentCertificateRotationStartParams,
    ) -> AgentClientCertificateRotation:
        self.start_requests.append(params)
        if self.before_start is not None:
            self.before_start(params)
        if self.response is None:
            self.response = self.output_mutator(
                _rotation_output(
                    request=params,
                    ca_key=self.ca_key,
                    ca_certificate=self.ca_certificate,
                ),
            )
        if self.start_error_count:
            self.start_error_count -= 1
            raise AgentApiClientError
        return self.response

    async def confirm_certificate_rotation(
        self,
        *,
        rotation_id: str,
    ) -> AgentCertificateRotationConfirmation:
        self.confirm_ids.append(rotation_id)
        if self.confirm_error_count:
            self.confirm_error_count -= 1
            raise AgentApiClientError
        return AgentCertificateRotationConfirmation(
            rotation_id=rotation_id,
            confirmed_at=NOW,
        )


def test_desktop_store_reads_only_safe_versioned_credentials(tmp_path: Path) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)

    pair = store.active_pair()

    assert pair.certificate_file == root / "versions" / INITIAL_ID / "certificate.pem"
    assert pair.private_key_file == root / "versions" / INITIAL_ID / "private-key.pem"
    assert isinstance(store, LocalAgentCredentialRotationStorage)


@pytest.mark.parametrize("unsafe_part", ["root-mode", "version-mode", "key-mode", "key-link"])
def test_desktop_store_fails_closed_for_unsafe_modes_and_links(
    tmp_path: Path,
    unsafe_part: str,
) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    version = root / "versions" / INITIAL_ID
    if unsafe_part == "root-mode":
        root.chmod(0o755)
    elif unsafe_part == "version-mode":
        version.chmod(0o755)
    elif unsafe_part == "key-mode":
        (version / "private-key.pem").chmod(0o644)
    else:
        key_file = version / "private-key.pem"
        real_key = root.parent / "stolen-key.pem"
        key_file.replace(real_key)
        key_file.symlink_to(real_key)

    with pytest.raises(AgentCredentialStoreError) as exc_info:
        _desktop_store(root=root).active_pair()

    assert str(exc_info.value) == "agent credential access failed"
    assert exc_info.value.__cause__ is None


@pytest.mark.parametrize(
    "target",
    [
        "/private/outside",
        "../versions/11111111111111111111111111111111",
        "outside/11111111111111111111111111111111",
    ],
)
def test_desktop_store_rejects_unsafe_current_symlink_targets(
    tmp_path: Path,
    target: str,
) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    (root / "current").unlink()
    (root / "current").symlink_to(target)

    with pytest.raises(AgentCredentialStoreError):
        _desktop_store(root=root).active_pair()


@pytest.mark.parametrize("invalid_pending", ["malformed", "wrong-mode", "symlink"])
def test_desktop_store_rejects_malformed_or_unsafe_pending_state(
    tmp_path: Path,
    invalid_pending: str,
) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    pending_file = root / "pending.json"
    if invalid_pending == "malformed":
        pending_file.write_text('{"phase":"prepared","csrPem":"PRIVATE-SECRET"}')
        pending_file.chmod(0o600)
    elif invalid_pending == "wrong-mode":
        pending_file.write_text("{}")
        pending_file.chmod(0o644)
    else:
        outside = root.parent / "pending.json"
        outside.write_text("{}")
        outside.chmod(0o600)
        pending_file.symlink_to(outside)

    with pytest.raises(AgentCredentialStoreError):
        _desktop_store(root=root).load_pending_rotation()


def test_desktop_store_rejects_pending_rotation_that_targets_active_version(
    tmp_path: Path,
) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    pending_file = root / "pending.json"
    pending_file.write_text(
        json.dumps(
            {
                "phase": "prepared",
                "rotationId": INITIAL_ID,
                "previousVersionId": INITIAL_ID,
                "csrPem": "invalid-but-never-processed",
            },
        ),
    )
    pending_file.chmod(0o600)

    with pytest.raises(AgentCredentialStoreError):
        _desktop_store(root=root).load_pending_rotation()


def test_external_store_is_read_only_and_does_not_create_state(tmp_path: Path) -> None:
    root, _ca_key, _ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    version = root / "versions" / INITIAL_ID
    store = ExternalAgentCredentialStore(
        certificate_file=version / "certificate.pem",
        private_key_file=version / "private-key.pem",
        private_key_mode=0o600,
    )

    pair = store.active_pair()

    assert pair.private_key_file == version / "private-key.pem"
    assert not isinstance(store, LocalAgentCredentialRotationStorage)
    assert not (root / "pending.json").exists()


@pytest.mark.asyncio
async def test_pending_rotation_is_durable_before_the_network_call(tmp_path: Path) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)
    remote = _remote(ca_key=ca_key, ca_certificate=ca_certificate)

    def assert_pending_first(request: AgentCertificateRotationStartParams) -> None:
        pending = json.loads((root / "pending.json").read_text())
        assert pending["rotationId"] == ROTATION_ID
        assert pending["previousVersionId"] == INITIAL_ID
        assert pending["csrPem"] == request.csr_pem
        key_file = root / "versions" / ROTATION_ID / "private-key.pem"
        assert key_file.is_file()
        assert key_file.stat().st_mode & 0o777 == 0o600
        assert (root / "current").readlink() == Path("versions") / INITIAL_ID

    remote.before_start = assert_pending_first
    coordinator = _coordinator(store=store, remote=remote)

    assert (
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
        is True
    )


@pytest.mark.asyncio
async def test_certificate_outside_rotation_window_is_a_noop(tmp_path: Path) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(
        tmp_path=tmp_path,
        expires_at=NOW + timedelta(days=15),
    )
    store = _desktop_store(root=root)
    remote = _remote(ca_key=ca_key, ca_certificate=ca_certificate)

    assert (
        await _coordinator(store=store, remote=remote).rotate_if_needed(
            current_datetime=NOW,
            policy=LOCAL_ROTATION_POLICY,
        )
        is False
    )
    assert remote.start_requests == []
    assert not (root / "pending.json").exists()


@pytest.mark.asyncio
async def test_lost_start_response_reuses_the_pending_id_key_and_csr(tmp_path: Path) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)
    remote = _remote(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        start_error_count=1,
    )
    coordinator = _coordinator(store=store, remote=remote)

    with pytest.raises(AgentApiClientError):
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
    pending_before = (root / "pending.json").read_bytes()
    key_before = (root / "versions" / ROTATION_ID / "private-key.pem").read_bytes()

    assert (
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
        is True
    )
    assert len(remote.start_requests) == 2
    assert remote.start_requests[0] == remote.start_requests[1]
    assert key_before not in pending_before
    assert remote.confirm_ids == [ROTATION_ID]


@pytest.mark.asyncio
async def test_crash_before_symlink_switch_resumes_without_a_second_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)
    remote = _remote(ca_key=ca_key, ca_certificate=ca_certificate)
    original_activate = DesktopAgentCredentialStore.activate_rotation
    failed = False

    def crash_once(
        current_store: DesktopAgentCredentialStore,
        *,
        rotation: IssuedLocalAgentCredentialRotation,
    ) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise AgentCredentialStoreError
        original_activate(current_store, rotation=rotation)

    monkeypatch.setattr(DesktopAgentCredentialStore, "activate_rotation", crash_once)
    coordinator = _coordinator(store=store, remote=remote)

    with pytest.raises(AgentCredentialStoreError):
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
    assert (root / "current").readlink() == Path("versions") / INITIAL_ID

    assert (
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
        is True
    )
    assert len(remote.start_requests) == 1
    assert (root / "current").readlink() == Path("versions") / ROTATION_ID


@pytest.mark.asyncio
async def test_restart_recovers_stale_atomic_switch_symlink(tmp_path: Path) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)
    remote = _remote(ca_key=ca_key, ca_certificate=ca_certificate)
    pending = store.prepare_rotation(rotation_id=ROTATION_ID)
    response = await remote.start_certificate_rotation(params=pending.to_start_params())
    store.persist_replacement(
        pending=pending,
        response=response,
        current_datetime=NOW,
    )
    stale_link = root / f".current.{ROTATION_ID}"
    stale_link.symlink_to(Path("versions") / ROTATION_ID)

    assert (
        await _coordinator(
            store=_desktop_store(root=root),
            remote=remote,
        ).rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
        is True
    )
    assert (root / "current").readlink() == Path("versions") / ROTATION_ID
    assert not stale_link.exists()


@pytest.mark.asyncio
async def test_lost_confirm_response_retries_with_the_new_pair(tmp_path: Path) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)
    remote = _remote(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        confirm_error_count=1,
    )
    coordinator = _coordinator(store=store, remote=remote)

    with pytest.raises(AgentApiClientError):
        await coordinator.rotate_if_needed(current_datetime=NOW, policy=LOCAL_ROTATION_POLICY)
    assert (root / "current").readlink() == Path("versions") / ROTATION_ID
    assert (root / "versions" / INITIAL_ID).exists()
    assert (root / "pending.json").exists()

    restarted_coordinator = _coordinator(
        store=_desktop_store(root=root),
        remote=remote,
    )

    assert (
        await restarted_coordinator.rotate_if_needed(
            current_datetime=NOW,
            policy=LOCAL_ROTATION_POLICY,
        )
        is True
    )
    assert len(remote.start_requests) == 1
    assert remote.confirm_ids == [ROTATION_ID, ROTATION_ID]
    assert _desktop_store(root=root).active_pair().private_key_file.parent.name == ROTATION_ID
    assert not (root / "versions" / INITIAL_ID).exists()
    assert not (root / "pending.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mismatch",
    ["fingerprint", "serial", "validity", "key", "eku", "chain", "wrong-signer"],
)
async def test_replacement_certificate_mismatches_fail_closed(
    tmp_path: Path,
    mismatch: str,
) -> None:
    root, ca_key, ca_certificate = _write_desktop_credentials(tmp_path=tmp_path)
    store = _desktop_store(root=root)

    def mutate(output: AgentClientCertificateRotation) -> AgentClientCertificateRotation:
        if mismatch == "fingerprint":
            return replace(output, fingerprint_sha256="0" * 64)
        if mismatch == "serial":
            return replace(output, serial_number="123")
        if mismatch == "validity":
            return replace(output, valid_from=NOW - timedelta(minutes=5))
        if mismatch == "chain":
            return replace(output, certificate_chain_pem="not a chain")
        if mismatch == "wrong-signer":
            _other_key, other_ca = _certificate_authority()
            return replace(
                output,
                certificate_chain_pem=other_ca.public_bytes(
                    serialization.Encoding.PEM,
                ).decode(),
            )
        leaf = x509.load_pem_x509_certificate(output.certificate_pem.encode())
        replacement_key = ec.generate_private_key(ec.SECP256R1())
        public_key = replacement_key.public_key() if mismatch == "key" else leaf.public_key()
        assert isinstance(public_key, ec.EllipticCurvePublicKey)
        eku = (
            [ExtendedKeyUsageOID.SERVER_AUTH]
            if mismatch == "eku"
            else [ExtendedKeyUsageOID.CLIENT_AUTH]
        )
        certificate = _issue_client_certificate(
            ca_key=ca_key,
            ca_certificate=ca_certificate,
            public_key=public_key,
            valid_from=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(days=90),
            eku=eku,
        )
        return replace(
            output,
            certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode(),
            fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
            serial_number=format(certificate.serial_number, "x"),
            valid_from=certificate.not_valid_before_utc,
            expires_at=certificate.not_valid_after_utc,
        )

    remote = _remote(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        output_mutator=mutate,
    )

    with pytest.raises(AgentCredentialCertificateValidationError) as exc_info:
        await _coordinator(store=store, remote=remote).rotate_if_needed(
            current_datetime=NOW,
            policy=LOCAL_ROTATION_POLICY,
        )

    assert str(exc_info.value) == "agent certificate validation failed"
    assert exc_info.value.__cause__ is None
    assert (root / "current").readlink() == Path("versions") / INITIAL_ID
    assert (root / "versions" / INITIAL_ID).exists()


def _desktop_store(*, root: Path) -> DesktopAgentCredentialStore:
    return DesktopAgentCredentialStore(
        credential_directory=root,
        directory_mode=0o700,
        private_key_mode=0o600,
        pending_file_mode=0o600,
        csr_pem_max_length=16_384,
    )


def _coordinator(
    *,
    store: DesktopAgentCredentialStore,
    remote: AgentApiRemoteStub,
) -> AutomaticAgentCredentialRotationUseCase:
    return AutomaticAgentCredentialRotationUseCase(
        storage=store,
        client=cast("AgentApiClient", remote),
        id_generator=HexUuidIdGenerator(lambda: ROTATION_ID),
    )


def _remote(
    *,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_certificate: x509.Certificate,
    output_mutator: Callable[
        [AgentClientCertificateRotation],
        AgentClientCertificateRotation,
    ] = lambda output: output,
    start_error_count: int = 0,
    confirm_error_count: int = 0,
) -> AgentApiRemoteStub:
    return AgentApiRemoteStub(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        output_mutator=output_mutator,
        start_error_count=start_error_count,
        confirm_error_count=confirm_error_count,
        start_requests=[],
        confirm_ids=[],
        before_start=None,
    )


def _write_desktop_credentials(
    *,
    tmp_path: Path,
    expires_at: datetime = NOW + timedelta(days=13),
) -> tuple[Path, ec.EllipticCurvePrivateKey, x509.Certificate]:
    root = tmp_path / "credentials"
    version = root / "versions" / INITIAL_ID
    version.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    (root / "versions").chmod(0o700)
    version.chmod(0o700)
    ca_key, ca_certificate = _certificate_authority()
    private_key = ec.generate_private_key(ec.SECP256R1())
    certificate = _issue_client_certificate(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        public_key=private_key.public_key(),
        valid_from=NOW - timedelta(days=77),
        expires_at=expires_at,
        eku=[ExtendedKeyUsageOID.CLIENT_AUTH],
    )
    (version / "private-key.pem").write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    (version / "private-key.pem").chmod(0o600)
    (version / "certificate.pem").write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
        + ca_certificate.public_bytes(serialization.Encoding.PEM),
    )
    (version / "certificate.pem").chmod(0o600)
    (root / "current").symlink_to(Path("versions") / INITIAL_ID)
    return root, ca_key, ca_certificate


def _certificate_authority() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Agent test CA")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - timedelta(days=1))
        .not_valid_after(NOW + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )
    return private_key, certificate


def _rotation_output(
    *,
    request: AgentCertificateRotationStartParams,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_certificate: x509.Certificate,
) -> AgentClientCertificateRotation:
    csr = x509.load_pem_x509_csr(request.csr_pem.encode())
    public_key = csr.public_key()
    assert isinstance(public_key, ec.EllipticCurvePublicKey)
    certificate = _issue_client_certificate(
        ca_key=ca_key,
        ca_certificate=ca_certificate,
        public_key=public_key,
        valid_from=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(days=90),
        eku=[ExtendedKeyUsageOID.CLIENT_AUTH],
    )
    return AgentClientCertificateRotation(
        certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode(),
        certificate_chain_pem=ca_certificate.public_bytes(serialization.Encoding.PEM).decode(),
        fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
        serial_number=format(certificate.serial_number, "x"),
        valid_from=certificate.not_valid_before_utc,
        expires_at=certificate.not_valid_after_utc,
        replayed=False,
    )


def _issue_client_certificate(  # noqa: PLR0913
    *,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_certificate: x509.Certificate,
    public_key: ec.EllipticCurvePublicKey,
    valid_from: datetime,
    expires_at: datetime,
    eku: list[x509.ObjectIdentifier],
) -> x509.Certificate:
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "agent:test")]))
        .issuer_name(ca_certificate.subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(expires_at)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage(eku), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
