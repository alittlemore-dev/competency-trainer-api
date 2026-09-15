from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.agent_access.exceptions import AgentCertificateRequestError
from core.agent_access.schemas import AgentCertificateIssueParams
from core.schemas import Secret
from infra.cryptography.agent_certificates import CryptographyAgentCertificateIssuer

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


class TestCryptographyAgentCertificateIssuer:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        issuer_key = ec.generate_private_key(ec.SECP256R1())
        issuer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Agent Issuing CA")])
        issuer_certificate = (
            x509.CertificateBuilder()
            .subject_name(issuer_name)
            .issuer_name(issuer_name)
            .public_key(issuer_key.public_key())
            .serial_number(1)
            .not_valid_before(NOW - timedelta(days=1))
            .not_valid_after(NOW + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(issuer_key, hashes.SHA256())
        )
        self.issuer_key = issuer_key
        self.issuer_certificate = issuer_certificate
        self.issuer = CryptographyAgentCertificateIssuer(
            issuing_certificate_pem=issuer_certificate.public_bytes(
                serialization.Encoding.PEM,
            ).decode(),
            issuing_private_key_pem=Secret(
                issuer_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode(),
            ),
            certificate_chain_pem=issuer_certificate.public_bytes(
                serialization.Encoding.PEM,
            ).decode(),
        )

    def test_issue_ignores_requested_identity_and_issues_client_auth_only(self) -> None:
        client_key = ec.generate_private_key(ec.SECP256R1())
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "owner")]))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("admin.example.com")]),
                critical=False,
            )
            .sign(client_key, hashes.SHA256())
        )

        issued = self.issuer.issue(
            params=AgentCertificateIssueParams(
                agent_client_id="00000000000000000000000000000001",
                csr_pem=csr.public_bytes(serialization.Encoding.PEM).decode(),
                valid_from=NOW,
                expires_at=NOW + timedelta(days=90),
            ),
        )

        certificate = x509.load_pem_x509_certificate(issued.certificate_pem.encode())
        assert certificate.subject == x509.Name(
            [
                x509.NameAttribute(
                    NameOID.COMMON_NAME,
                    "agent:00000000000000000000000000000001",
                ),
            ],
        )
        assert certificate.issuer == self.issuer_certificate.subject
        certificate_public_key = certificate.public_key()
        assert isinstance(certificate_public_key, ec.EllipticCurvePublicKey)
        assert certificate_public_key.public_numbers() == client_key.public_key().public_numbers()
        assert certificate.not_valid_before_utc == NOW
        assert certificate.not_valid_after_utc == NOW + timedelta(days=90)
        assert certificate.extensions.get_extension_for_class(
            x509.ExtendedKeyUsage,
        ).value == x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH])
        assert certificate.extensions.get_extension_for_class(
            x509.BasicConstraints,
        ).value == x509.BasicConstraints(ca=False, path_length=None)
        with pytest.raises(x509.ExtensionNotFound):
            certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        assert issued.fingerprint_sha256 == certificate.fingerprint(hashes.SHA256()).hex()
        assert issued.serial_number == format(certificate.serial_number, "x")
        assert (
            issued.certificate_chain_pem
            == self.issuer_certificate.public_bytes(
                serialization.Encoding.PEM,
            ).decode()
        )
        assert self.issuer.get_certificate_chain_pem() == issued.certificate_chain_pem

    def test_issue_rejects_non_p256_client_key(self) -> None:
        client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "runner")]))
            .sign(client_key, hashes.SHA256())
        )

        with pytest.raises(AgentCertificateRequestError):
            self.issuer.issue(
                params=AgentCertificateIssueParams(
                    agent_client_id="00000000000000000000000000000001",
                    csr_pem=csr.public_bytes(serialization.Encoding.PEM).decode(),
                    valid_from=NOW,
                    expires_at=NOW + timedelta(days=90),
                ),
            )

    def test_constructor_rejects_matching_key_for_non_ca_certificate(self) -> None:
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Not a CA")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(self.issuer_key.public_key())
            .serial_number(2)
            .not_valid_before(NOW - timedelta(days=1))
            .not_valid_after(NOW + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.issuer_key, hashes.SHA256())
        )

        with pytest.raises(AgentCertificateRequestError):
            CryptographyAgentCertificateIssuer(
                issuing_certificate_pem=certificate.public_bytes(
                    serialization.Encoding.PEM,
                ).decode(),
                issuing_private_key_pem=Secret(
                    self.issuer_key.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption(),
                    ).decode(),
                ),
                certificate_chain_pem=self.issuer_certificate.public_bytes(
                    serialization.Encoding.PEM,
                ).decode(),
            )

    def test_issue_rejects_validity_outside_issuing_certificate(self) -> None:
        client_key = ec.generate_private_key(ec.SECP256R1())
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "runner")]))
            .sign(client_key, hashes.SHA256())
        )

        with pytest.raises(AgentCertificateRequestError):
            self.issuer.issue(
                params=AgentCertificateIssueParams(
                    agent_client_id="00000000000000000000000000000001",
                    csr_pem=csr.public_bytes(serialization.Encoding.PEM).decode(),
                    valid_from=NOW,
                    expires_at=self.issuer_certificate.not_valid_after_utc + timedelta(seconds=1),
                ),
            )

    @pytest.mark.parametrize("chain_mode", ["empty", "contains-private-key"])
    def test_constructor_rejects_unsafe_certificate_chain(self, chain_mode: str) -> None:
        private_key_pem = self.issuer_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        certificate_pem = self.issuer_certificate.public_bytes(
            serialization.Encoding.PEM,
        ).decode()
        chain_pem = "" if chain_mode == "empty" else certificate_pem + private_key_pem

        with pytest.raises(AgentCertificateRequestError):
            CryptographyAgentCertificateIssuer(
                issuing_certificate_pem=certificate_pem,
                issuing_private_key_pem=Secret(private_key_pem),
                certificate_chain_pem=chain_pem,
            )
