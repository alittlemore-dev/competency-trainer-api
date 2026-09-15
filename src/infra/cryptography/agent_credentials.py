import json
import os
import re
import stat
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Literal, TypeGuard

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from core.agent_access.exceptions import (
    AgentCredentialCertificateValidationError,
    AgentCredentialStoreError,
)
from core.agent_access.schemas import (
    AgentClientCertificateRotation,
    IssuedLocalAgentCredentialRotation,
    PreparedLocalAgentCredentialRotation,
)
from core.agent_access.storages import LocalAgentCredentialRotationStorage

_VERSION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_CURRENT_TARGET_PART_COUNT = 2
_CERTIFICATE_PATTERN = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    flags=re.DOTALL,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCredentialPair:
    certificate_file: Path
    private_key_file: Path


class AgentCredentialPairProvider(ABC):
    @abstractmethod
    def active_pair(self) -> AgentCredentialPair:
        raise NotImplementedError


class PendingAgentCredentialRotationDtoBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="forbid", populate_by_name=True)

    rotation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    previous_version_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    csr_pem: str = Field(min_length=1, repr=False)


class PreparedAgentCredentialRotationDto(PendingAgentCredentialRotationDtoBase):
    phase: Literal["prepared"]

    def to_domain_schema(self) -> PreparedLocalAgentCredentialRotation:
        return PreparedLocalAgentCredentialRotation(
            rotation_id=self.rotation_id,
            previous_version_id=self.previous_version_id,
            csr_pem=self.csr_pem,
        )

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: PreparedLocalAgentCredentialRotation,
    ) -> PreparedAgentCredentialRotationDto:
        return cls(
            phase="prepared",
            rotation_id=schema.rotation_id,
            previous_version_id=schema.previous_version_id,
            csr_pem=schema.csr_pem,
        )


class IssuedAgentCredentialRotationDto(PendingAgentCredentialRotationDtoBase):
    phase: Literal["issued"]
    fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    serial_number: str = Field(pattern=r"^[0-9a-f]+$")
    valid_from: datetime
    expires_at: datetime

    def to_domain_schema(self) -> IssuedLocalAgentCredentialRotation:
        return IssuedLocalAgentCredentialRotation(
            rotation_id=self.rotation_id,
            previous_version_id=self.previous_version_id,
            csr_pem=self.csr_pem,
            fingerprint_sha256=self.fingerprint_sha256,
            serial_number=self.serial_number,
            valid_from=self.valid_from,
            expires_at=self.expires_at,
        )

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: IssuedLocalAgentCredentialRotation,
    ) -> IssuedAgentCredentialRotationDto:
        return cls(
            phase="issued",
            rotation_id=schema.rotation_id,
            previous_version_id=schema.previous_version_id,
            csr_pem=schema.csr_pem,
            fingerprint_sha256=schema.fingerprint_sha256,
            serial_number=schema.serial_number,
            valid_from=schema.valid_from,
            expires_at=schema.expires_at,
        )


type PendingAgentCredentialRotation = (
    PreparedAgentCredentialRotationDto | IssuedAgentCredentialRotationDto
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalAgentCredentialStore(AgentCredentialPairProvider):
    certificate_file: Path
    private_key_file: Path
    private_key_mode: int

    def active_pair(self) -> AgentCredentialPair:
        try:
            _require_absolute_regular_file(path=self.certificate_file, required_mode=None)
            _require_absolute_regular_file(
                path=self.private_key_file,
                required_mode=self.private_key_mode,
            )
            _validate_credential_pair(
                certificate_file=self.certificate_file,
                private_key_file=self.private_key_file,
            )
        except OSError, UnsupportedAlgorithm, TypeError, ValueError, x509.ExtensionNotFound:
            raise AgentCredentialStoreError from None
        return AgentCredentialPair(
            certificate_file=self.certificate_file,
            private_key_file=self.private_key_file,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DesktopAgentCredentialStore(
    AgentCredentialPairProvider,
    LocalAgentCredentialRotationStorage,
):
    credential_directory: Path
    directory_mode: int
    private_key_mode: int
    pending_file_mode: int
    csr_pem_max_length: int

    @property
    def _versions_directory(self) -> Path:
        return self.credential_directory / "versions"

    @property
    def _current_link(self) -> Path:
        return self.credential_directory / "current"

    @property
    def _pending_file(self) -> Path:
        return self.credential_directory / "pending.json"

    def active_pair(self) -> AgentCredentialPair:
        try:
            self._validate_base_layout()
            version_id = self._read_current_version_id()
            return self._validated_pair(version_id=version_id)
        except OSError, UnsupportedAlgorithm, TypeError, ValueError, x509.ExtensionNotFound:
            raise AgentCredentialStoreError from None

    def get_active_certificate_expires_at(self) -> datetime:
        pair = self.active_pair()
        try:
            certificate, _chain = _load_certificate_chain(path=pair.certificate_file)
        except OSError, UnsupportedAlgorithm, TypeError, ValueError:
            raise AgentCredentialStoreError from None
        return certificate.not_valid_after_utc

    def load_pending_rotation(
        self,
    ) -> PreparedLocalAgentCredentialRotation | IssuedLocalAgentCredentialRotation | None:
        try:
            pending = self._load_pending()
        except (
            OSError,
            UnsupportedAlgorithm,
            TypeError,
            ValueError,
            ValidationError,
            x509.ExtensionNotFound,
        ):
            raise AgentCredentialStoreError from None
        else:
            return None if pending is None else pending.to_domain_schema()

    def prepare_rotation(
        self,
        *,
        rotation_id: str,
    ) -> PreparedLocalAgentCredentialRotation:
        try:
            pending = self._prepare_rotation(rotation_id=rotation_id)
        except OSError, UnsupportedAlgorithm, TypeError, ValueError, ValidationError:
            raise AgentCredentialStoreError from None
        else:
            return pending.to_domain_schema()

    def persist_replacement(
        self,
        *,
        pending: PreparedLocalAgentCredentialRotation,
        response: AgentClientCertificateRotation,
        current_datetime: datetime,
    ) -> IssuedLocalAgentCredentialRotation:
        pending_dto = PreparedAgentCredentialRotationDto.from_domain_schema(schema=pending)
        try:
            certificate_chain = self._validate_replacement(
                pending=pending_dto,
                response=response,
                current_datetime=current_datetime,
            )
            certificate_file = (
                self._version_directory(
                    version_id=pending.rotation_id,
                )
                / "certificate.pem"
            )
            _atomic_write(
                path=certificate_file,
                content=certificate_chain,
                mode=self.pending_file_mode,
            )
            issued = IssuedAgentCredentialRotationDto(
                phase="issued",
                rotation_id=pending.rotation_id,
                previous_version_id=pending.previous_version_id,
                csr_pem=pending.csr_pem,
                fingerprint_sha256=response.fingerprint_sha256,
                serial_number=response.serial_number,
                valid_from=response.valid_from,
                expires_at=response.expires_at,
            )
            self._write_pending(pending=issued)
            self._validate_issued_pair_safely(
                pending=issued,
                current_datetime=current_datetime,
            )
        except AgentCredentialCertificateValidationError:
            raise
        except OSError, UnsupportedAlgorithm, TypeError, ValueError, ValidationError:
            raise AgentCredentialStoreError from None
        else:
            return issued.to_domain_schema()

    def _validate_issued_pair_safely(
        self,
        *,
        pending: IssuedAgentCredentialRotationDto,
        current_datetime: datetime | None,
    ) -> AgentCredentialPair:
        try:
            pair = self._validate_issued_pair(
                pending=pending,
                current_datetime=current_datetime,
            )
        except OSError, UnsupportedAlgorithm, TypeError, ValueError, x509.ExtensionNotFound:
            raise AgentCredentialCertificateValidationError from None
        else:
            return pair

    def is_rotation_active(self, *, rotation_id: str) -> bool:
        try:
            return self._read_current_version_id() == rotation_id
        except OSError, TypeError, ValueError:
            raise AgentCredentialStoreError from None

    def activate_rotation(self, *, rotation: IssuedLocalAgentCredentialRotation) -> None:
        pending = IssuedAgentCredentialRotationDto.from_domain_schema(schema=rotation)
        try:
            persisted = self._load_pending()
            _require_matching_pending(value=persisted, expected=pending)
            self._validate_issued_pair_safely(pending=pending, current_datetime=None)
            temporary_link = self.credential_directory / f".current.{pending.rotation_id}"
            expected_target = Path("versions") / pending.rotation_id
            try:
                temporary_stat = temporary_link.lstat()
            except FileNotFoundError:
                pass
            else:
                _require_temporary_link_target(
                    path=temporary_link,
                    file_mode=temporary_stat.st_mode,
                    expected_target=expected_target,
                )
                temporary_link.unlink()
            try:
                temporary_link.symlink_to(expected_target)
                temporary_link.replace(self._current_link)
            finally:
                if temporary_link.is_symlink():
                    temporary_link.unlink()
            _fsync_directory(path=self.credential_directory)
        except AgentCredentialCertificateValidationError:
            raise
        except OSError, TypeError, ValueError:
            raise AgentCredentialStoreError from None

    def complete_rotation(self, *, rotation: IssuedLocalAgentCredentialRotation) -> None:
        pending = IssuedAgentCredentialRotationDto.from_domain_schema(schema=rotation)
        try:
            persisted = self._load_pending()
            _require_matching_pending(value=persisted, expected=pending)
            _require_equal(
                value=self._read_current_version_id(),
                expected=pending.rotation_id,
            )
            previous_directory = self._version_directory(
                version_id=pending.previous_version_id,
            )
            if previous_directory.exists() or previous_directory.is_symlink():
                _require_directory(
                    path=previous_directory,
                    required_mode=self.directory_mode,
                )
                for filename in ("private-key.pem", "certificate.pem"):
                    file_path = previous_directory / filename
                    if file_path.exists() or file_path.is_symlink():
                        _require_regular_file(path=file_path, required_mode=None)
                        file_path.unlink()
                previous_directory.rmdir()
            _fsync_directory(path=self._versions_directory)
            self._pending_file.unlink()
            _fsync_directory(path=self.credential_directory)
        except OSError, TypeError, ValueError:
            raise AgentCredentialStoreError from None

    def _validate_replacement(
        self,
        *,
        pending: PreparedAgentCredentialRotationDto,
        response: AgentClientCertificateRotation,
        current_datetime: datetime,
    ) -> bytes:
        try:
            certificate_chain = self._validate_replacement_content(
                pending=pending,
                response=response,
                current_datetime=current_datetime,
            )
        except (
            InvalidSignature,
            UnsupportedAlgorithm,
            TypeError,
            ValueError,
            x509.ExtensionNotFound,
        ):
            raise AgentCredentialCertificateValidationError from None
        else:
            return certificate_chain

    def _load_pending(self) -> PendingAgentCredentialRotation | None:
        self._validate_base_layout()
        if not self._pending_file.exists() and not self._pending_file.is_symlink():
            return None
        _require_regular_file(
            path=self._pending_file,
            required_mode=self.pending_file_mode,
        )
        raw = json.loads(self._pending_file.read_bytes())
        if not isinstance(raw, dict):
            raise TypeError
        if raw.get("phase") == "prepared":
            pending: PendingAgentCredentialRotation = (
                PreparedAgentCredentialRotationDto.model_validate(raw)
            )
        elif raw.get("phase") == "issued":
            pending = IssuedAgentCredentialRotationDto.model_validate(raw)
        else:
            raise ValueError
        if len(pending.csr_pem) > self.csr_pem_max_length:
            raise ValueError
        if pending.rotation_id == pending.previous_version_id:
            raise ValueError
        current_id = self._read_current_version_id()
        if current_id not in {pending.previous_version_id, pending.rotation_id}:
            raise ValueError
        self._validated_pending_private_key(pending=pending)
        if isinstance(pending, IssuedAgentCredentialRotationDto):
            self._validate_issued_pair_safely(pending=pending, current_datetime=None)
        return pending

    def _prepare_rotation(self, *, rotation_id: str) -> PreparedAgentCredentialRotationDto:
        self._validate_base_layout()
        if (
            self._pending_file.exists()
            or self._pending_file.is_symlink()
            or not _VERSION_ID_PATTERN.fullmatch(rotation_id)
        ):
            raise ValueError
        previous_version_id = self._read_current_version_id()
        version_directory = self._version_directory(version_id=rotation_id)
        version_directory.mkdir(mode=self.directory_mode)
        version_directory.chmod(self.directory_mode)
        _fsync_directory(path=self._versions_directory)
        private_key = ec.generate_private_key(ec.SECP256R1())
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name(
                    [x509.NameAttribute(NameOID.COMMON_NAME, "ignored-by-server")],
                ),
            )
            .sign(private_key, hashes.SHA256())
        )
        _atomic_write(
            path=version_directory / "private-key.pem",
            content=private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            mode=self.private_key_mode,
        )
        pending = PreparedAgentCredentialRotationDto(
            phase="prepared",
            rotation_id=rotation_id,
            previous_version_id=previous_version_id,
            csr_pem=csr.public_bytes(serialization.Encoding.PEM).decode(),
        )
        if len(pending.csr_pem) > self.csr_pem_max_length:
            raise ValueError
        self._write_pending(pending=pending)
        self._validated_pending_private_key(pending=pending)
        return pending

    def _validate_issued_pair(
        self,
        *,
        pending: IssuedAgentCredentialRotationDto,
        current_datetime: datetime | None,
    ) -> AgentCredentialPair:
        pair = self._validated_pair(version_id=pending.rotation_id)
        certificate, _chain = _load_certificate_chain(path=pair.certificate_file)
        if (
            certificate.fingerprint(hashes.SHA256()).hex() != pending.fingerprint_sha256
            or format(certificate.serial_number, "x") != pending.serial_number
            or certificate.not_valid_before_utc != pending.valid_from
            or certificate.not_valid_after_utc != pending.expires_at
        ):
            raise ValueError
        if current_datetime is not None and not (
            certificate.not_valid_before_utc <= current_datetime < certificate.not_valid_after_utc
        ):
            raise ValueError
        return pair

    def _validate_replacement_content(
        self,
        *,
        pending: PreparedAgentCredentialRotationDto,
        response: AgentClientCertificateRotation,
        current_datetime: datetime,
    ) -> bytes:
        leaf_certificates = _parse_certificate_chain(content=response.certificate_pem.encode())
        if len(leaf_certificates) != 1:
            raise ValueError
        certificate = leaf_certificates[0]
        private_key = self._validated_pending_private_key(pending=pending)
        csr = x509.load_pem_x509_csr(pending.csr_pem.encode())
        certificate_public_key = certificate.public_key()
        csr_public_key = csr.public_key()
        if (
            not csr.is_signature_valid
            or not _is_p256_public_key(certificate_public_key)
            or not _is_p256_public_key(csr_public_key)
            or certificate_public_key.public_numbers() != private_key.public_key().public_numbers()
            or csr_public_key.public_numbers() != private_key.public_key().public_numbers()
            or certificate.fingerprint(hashes.SHA256()).hex() != response.fingerprint_sha256
            or format(certificate.serial_number, "x") != response.serial_number
            or certificate.not_valid_before_utc != response.valid_from
            or certificate.not_valid_after_utc != response.expires_at
            or not (
                certificate.not_valid_before_utc
                <= current_datetime
                < certificate.not_valid_after_utc
            )
        ):
            raise ValueError
        extended_key_usage = certificate.extensions.get_extension_for_class(
            x509.ExtendedKeyUsage,
        ).value
        if list(extended_key_usage) != [ExtendedKeyUsageOID.CLIENT_AUTH]:
            raise ValueError
        chain_certificates = _parse_certificate_chain(
            content=response.certificate_chain_pem.encode(),
        )
        if not chain_certificates:
            raise ValueError
        for chain_certificate in chain_certificates:
            constraints = chain_certificate.extensions.get_extension_for_class(
                x509.BasicConstraints,
            ).value
            if not constraints.ca or not (
                chain_certificate.not_valid_before_utc
                <= current_datetime
                < chain_certificate.not_valid_after_utc
            ):
                raise ValueError
        certificate.verify_directly_issued_by(chain_certificates[0])
        for child, issuer in pairwise(chain_certificates):
            child.verify_directly_issued_by(issuer)
        return (
            response.certificate_pem.rstrip() + "\n" + response.certificate_chain_pem.lstrip()
        ).encode()

    def _validated_pending_private_key(
        self,
        *,
        pending: PendingAgentCredentialRotation,
    ) -> ec.EllipticCurvePrivateKey:
        version_directory = self._version_directory(version_id=pending.rotation_id)
        _require_directory(path=version_directory, required_mode=self.directory_mode)
        key_file = version_directory / "private-key.pem"
        _require_regular_file(path=key_file, required_mode=self.private_key_mode)
        private_key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
            private_key.curve,
            ec.SECP256R1,
        ):
            raise TypeError
        return private_key

    def _validated_pair(self, *, version_id: str) -> AgentCredentialPair:
        version_directory = self._version_directory(version_id=version_id)
        _require_directory(path=version_directory, required_mode=self.directory_mode)
        pair = AgentCredentialPair(
            certificate_file=version_directory / "certificate.pem",
            private_key_file=version_directory / "private-key.pem",
        )
        _require_regular_file(path=pair.certificate_file, required_mode=self.pending_file_mode)
        _require_regular_file(path=pair.private_key_file, required_mode=self.private_key_mode)
        _validate_credential_pair(
            certificate_file=pair.certificate_file,
            private_key_file=pair.private_key_file,
        )
        return pair

    def _validate_base_layout(self) -> None:
        if not self.credential_directory.is_absolute():
            raise ValueError
        _require_directory(
            path=self.credential_directory,
            required_mode=self.directory_mode,
        )
        _require_directory(path=self._versions_directory, required_mode=self.directory_mode)

    def _read_current_version_id(self) -> str:
        link_stat = self._current_link.lstat()
        if not stat.S_ISLNK(link_stat.st_mode):
            raise ValueError
        target_path = self._current_link.readlink()
        if (
            target_path.is_absolute()
            or len(target_path.parts) != _CURRENT_TARGET_PART_COUNT
            or target_path.parts[0] != "versions"
            or not _VERSION_ID_PATTERN.fullmatch(target_path.parts[1])
        ):
            raise ValueError
        version_id = target_path.parts[1]
        _require_directory(
            path=self._version_directory(version_id=version_id),
            required_mode=self.directory_mode,
        )
        return version_id

    def _version_directory(self, *, version_id: str) -> Path:
        if not _VERSION_ID_PATTERN.fullmatch(version_id):
            raise ValueError
        return self._versions_directory / version_id

    def _write_pending(self, *, pending: PendingAgentCredentialRotation) -> None:
        _atomic_write(
            path=self._pending_file,
            content=pending.model_dump_json(by_alias=True).encode(),
            mode=self.pending_file_mode,
        )


def _require_absolute_regular_file(*, path: Path, required_mode: int | None) -> None:
    if not path.is_absolute():
        raise ValueError
    _require_regular_file(path=path, required_mode=required_mode)


def _require_regular_file(*, path: Path, required_mode: int | None) -> None:
    file_stat = path.lstat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError
    if required_mode is not None and stat.S_IMODE(file_stat.st_mode) != required_mode:
        raise ValueError


def _require_directory(*, path: Path, required_mode: int) -> None:
    directory_stat = path.lstat()
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or stat.S_IMODE(directory_stat.st_mode) != required_mode
    ):
        raise ValueError


def _require_temporary_link_target(
    *,
    path: Path,
    file_mode: int,
    expected_target: Path,
) -> None:
    if not stat.S_ISLNK(file_mode) or path.readlink() != expected_target:
        raise ValueError


def _require_equal(*, value: str, expected: str) -> None:
    if value != expected:
        raise ValueError


def _require_matching_pending(
    *,
    value: PendingAgentCredentialRotation | None,
    expected: PendingAgentCredentialRotation,
) -> None:
    if value != expected:
        raise ValueError


def _validate_credential_pair(*, certificate_file: Path, private_key_file: Path) -> None:
    certificate, _chain = _load_certificate_chain(path=certificate_file)
    private_key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    public_key = certificate.public_key()
    if (
        not isinstance(private_key, ec.EllipticCurvePrivateKey)
        or not isinstance(private_key.curve, ec.SECP256R1)
        or not _is_p256_public_key(public_key)
        or public_key.public_numbers() != private_key.public_key().public_numbers()
    ):
        raise ValueError
    extended_key_usage = certificate.extensions.get_extension_for_class(
        x509.ExtendedKeyUsage,
    ).value
    if list(extended_key_usage) != [ExtendedKeyUsageOID.CLIENT_AUTH]:
        raise ValueError


def _load_certificate_chain(*, path: Path) -> tuple[x509.Certificate, list[x509.Certificate]]:
    certificates = _parse_certificate_chain(content=path.read_bytes())
    if not certificates:
        raise ValueError
    return certificates[0], certificates[1:]


def _parse_certificate_chain(*, content: bytes) -> list[x509.Certificate]:
    blocks = _CERTIFICATE_PATTERN.findall(content)
    remainder = content
    for block in blocks:
        remainder = remainder.replace(block, b"", 1)
    if not blocks or remainder.strip():
        raise ValueError
    return [x509.load_pem_x509_certificate(block) for block in blocks]


def _is_p256_public_key(public_key: object) -> TypeGuard[ec.EllipticCurvePublicKey]:
    return isinstance(public_key, ec.EllipticCurvePublicKey) and isinstance(
        public_key.curve,
        ec.SECP256R1,
    )


def _atomic_write(*, path: Path, content: bytes, mode: int) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.chmod(mode)
        temporary_path.replace(path)
        _fsync_directory(path=path.parent)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _fsync_directory(*, path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
