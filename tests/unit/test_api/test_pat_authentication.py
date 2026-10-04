import pytest
from backend_sdk import AuthenticationResult, CredentialTypeEnum, Principal, RoleEnum
from backend_sdk.auth.testing import FakeAuthenticationClient, bearer_headers
from litestar import Litestar
from litestar.testing import TestClient


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/admin/articles"),
        ("POST", "/api/admin/articles"),
        ("GET", "/api/admin/competency-matrix/items"),
        ("DELETE", "/api/admin/files/test"),
        ("POST", "/api/admin/tools/cache/clear"),
    ],
)
def test_pat_missing_domain_permission_is_denied(
    sdk_auth_app: Litestar,
    sdk_authentication_client: FakeAuthenticationClient,
    method: str,
    path: str,
) -> None:
    sdk_authentication_client.set_result(
        AuthenticationResult(
            principal=Principal(username="owner", role=RoleEnum.OWNER),
            valid_for_seconds=3600,
            credential_type=CredentialTypeEnum.PAT,
            credential_id="test",
            permissions=frozenset({"workspace.resumes.read"}),
            cache_ttl_seconds=0,
        )
    )
    with TestClient(sdk_auth_app) as client:
        response = client.request(method, path, headers=pat_headers())
    assert response.status_code == 403


def test_pat_permission_does_not_bypass_current_role(
    sdk_auth_app: Litestar,
    sdk_authentication_client: FakeAuthenticationClient,
) -> None:
    sdk_authentication_client.set_result(
        AuthenticationResult(
            principal=Principal(username="user", role=RoleEnum.USER),
            valid_for_seconds=3600,
            credential_type=CredentialTypeEnum.PAT,
            credential_id="test",
            permissions=frozenset({"competency.articles.read"}),
            cache_ttl_seconds=0,
        )
    )
    with TestClient(sdk_auth_app) as client:
        response = client.get("/api/admin/articles", headers=pat_headers())
    assert response.status_code == 403


def pat_headers() -> dict[str, str]:
    return bearer_headers(token="alm_pat_fixture")  # noqa: S106
