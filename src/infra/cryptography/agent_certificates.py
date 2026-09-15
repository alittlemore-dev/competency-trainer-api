import re
from dataclasses import dataclass, field
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.agent_access.clients import AgentCertificateIssuer
from core.agent_access.exceptions import AgentAuthenticationError, AgentCertificateRequestError
from core.agent_access.schemas import AgentCertificateIssueParams, IssuedAgentCertificate
from core.schemas import Secret


def parse_agent_certificate_fingerprint(*, escaped_certificate_pem: str) -> str:
    if not escaped_certificate_pem:
        raise AgentAuthenticationError
    try:
        certificate = x509.load_pem_x509_certificate(
            unquote(escaped_certificate_pem).encode(),
        )
    except ValueError as error:
        raise AgentAuthenticationError from error
    return certificate.fingerprint(hashes.SHA256()).hex()


@dataclass(frozen=True, slots=True, kw_only=True)
class CryptographyAgentCertificateIssuer(AgentCertificateIssuer):
    issuing_certificate_pem: str
    issuing_private_key_pem: Secret[str]
    certificate_chain_pem: str
    _issuing_certificate: x509.Certificate = field(init=False, repr=False)
    _issuing_private_key: ec.EllipticCurvePrivateKey = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            certificate = x509.load_pem_x509_certificate(
                self.issuing_certificate_pem.encode(),
            )
            private_key = serialization.load_pem_private_key(
                self.issuing_private_key_pem.get_secret_value().encode(),
                password=None,
            )
        except (TypeError, ValueError) as error:
            raise AgentCertificateRequestError from error
        if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
            private_key.curve,
            ec.SECP256R1,
        ):
            raise AgentCertificateRequestError
        certificate_public_key = certificate.public_key()
        if (
            not isinstance(certificate_public_key, ec.EllipticCurvePublicKey)
            or not isinstance(certificate_public_key.curve, ec.SECP256R1)
            or certificate_public_key.public_numbers() != private_key.public_key().public_numbers()
        ):
            raise AgentCertificateRequestError
        try:
            basic_constraints = certificate.extensions.get_extension_for_class(
                x509.BasicConstraints,
            ).value
            key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        except x509.ExtensionNotFound as error:
            raise AgentCertificateRequestError from error
        if not basic_constraints.ca or not key_usage.key_cert_sign:
            raise AgentCertificateRequestError
        chain_bytes = self.certificate_chain_pem.encode()
        certificate_blocks = re.findall(
            rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
            chain_bytes,
            flags=re.DOTALL,
        )
        remaining_chain = chain_bytes
        for certificate_block in certificate_blocks:
            remaining_chain = remaining_chain.replace(certificate_block, b"", 1)
        if not certificate_blocks or remaining_chain.strip():
            raise AgentCertificateRequestError
        try:
            chain_certificates = [
                x509.load_pem_x509_certificate(certificate_block)
                for certificate_block in certificate_blocks
            ]
            chain_ca_constraints = [
                chain_certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
                for chain_certificate in chain_certificates
            ]
        except (ValueError, x509.ExtensionNotFound) as error:
            raise AgentCertificateRequestError from error
        if chain_certificates[0].fingerprint(hashes.SHA256()) != certificate.fingerprint(
            hashes.SHA256()
        ) or not all(constraints.ca for constraints in chain_ca_constraints):
            raise AgentCertificateRequestError
        object.__setattr__(self, "_issuing_certificate", certificate)
        object.__setattr__(self, "_issuing_private_key", private_key)

    def issue(self, *, params: AgentCertificateIssueParams) -> IssuedAgentCertificate:
        try:
            csr = x509.load_pem_x509_csr(params.csr_pem.encode())
        except ValueError as error:
            raise AgentCertificateRequestError from error
        public_key = csr.public_key()
        if (
            not csr.is_signature_valid
            or not isinstance(public_key, ec.EllipticCurvePublicKey)
            or not isinstance(public_key.curve, ec.SECP256R1)
            or params.valid_from >= params.expires_at
            or params.valid_from < self._issuing_certificate.not_valid_before_utc
            or params.expires_at > self._issuing_certificate.not_valid_after_utc
        ):
            raise AgentCertificateRequestError
        certificate = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME,
                            f"agent:{params.agent_client_id}",
                        ),
                    ],
                ),
            )
            .issuer_name(self._issuing_certificate.subject)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(params.valid_from)
            .not_valid_after(params.expires_at)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(public_key),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self._issuing_private_key.public_key(),
                ),
                critical=False,
            )
            .sign(private_key=self._issuing_private_key, algorithm=hashes.SHA256())
        )
        return IssuedAgentCertificate(
            certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode(),
            certificate_chain_pem=self.certificate_chain_pem,
            fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
            serial_number=format(certificate.serial_number, "x"),
            valid_from=params.valid_from,
            expires_at=params.expires_at,
        )

    def get_certificate_chain_pem(self) -> str:
        return self.certificate_chain_pem
