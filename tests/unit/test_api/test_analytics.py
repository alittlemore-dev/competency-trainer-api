from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from backend_sdk.auth import RoleEnum
from backend_sdk.auth.testing import FakeAuthenticationClient
from dishka import AsyncContainer

from core.analytics.use_cases import AnalyticsUseCase
from tests.helpers.api import APIHelper


@pytest.mark.parametrize(
    ("role", "status"), [(RoleEnum.USER, 403), (RoleEnum.MODERATOR, 200), (RoleEnum.ADMIN, 200)]
)
def test_report_access(
    sdk_auth_api: APIHelper,
    sdk_authentication_client: FakeAuthenticationClient,
    role: RoleEnum,
    status: int,
) -> None:
    sdk_authentication_client.set_authenticated(username="visitor", role=role)
    sdk_auth_api.client.headers["Authorization"] = "Bearer test-token"
    response = sdk_auth_api.client.get(
        "/api/admin/analytics/report",
        params={
            "kind": "Site",
            "dateFrom": "2026-01-01",
            "dateTo": "2026-01-31",
            "language": "ru",
        },
    )
    assert response.status_code == status, response.content


def test_anonymous_report_is_protected(sdk_auth_api: APIHelper) -> None:
    response = sdk_auth_api.client.get(
        "/api/admin/analytics/report",
        params={
            "kind": "Site",
            "dateFrom": "2026-01-01",
            "dateTo": "2026-01-31",
            "language": "ru",
        },
    )
    assert response.status_code == 401, response.content


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [("2026-02-01", "2026-01-01"), ("2020-01-01", "2026-01-01"), ("2026-01-01", "2099-01-01")],
)
def test_invalid_report_range(
    sdk_auth_api: APIHelper,
    sdk_authentication_client: FakeAuthenticationClient,
    date_from: str,
    date_to: str,
) -> None:
    sdk_authentication_client.set_authenticated(username="admin", role=RoleEnum.ADMIN)
    sdk_auth_api.client.headers["Authorization"] = "Bearer test-token"
    response = sdk_auth_api.client.get(
        "/api/admin/analytics/report",
        params={
            "kind": "Site",
            "dateFrom": date_from,
            "dateTo": date_to,
            "language": "en",
        },
    )
    assert response.status_code == 400, response.content


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        ("Articles", "private-article"),
        ("Site", "/account?email=secret"),
        ("Matrix", "invalid-target"),
    ],
)
def test_reject_unbounded_tracking_targets(sdk_auth_api: APIHelper, kind: str, target: str) -> None:
    response = sdk_auth_api.client.post(
        "/api/analytics/visits",
        json={
            "kind": kind,
            "targetId": target,
            "source": "Direct",
            "event": "View",
            "visitorToken": "00000000-0000-4000-8000-000000000001",
            "visitToken": "00000000-0000-4000-8000-000000000002",
        },
    )
    assert response.status_code == 400, response.content


async def test_anonymous_tracking_and_dnt(
    sdk_auth_api: APIHelper, container: AsyncContainer
) -> None:
    use_case = await container.get(AnalyticsUseCase)
    assert isinstance(use_case, Mock)
    payload = {
        "kind": "Site",
        "targetId": "articles",
        "source": "Search",
        "event": "View",
        "visitorToken": "00000000-0000-4000-8000-000000000001",
        "visitToken": "00000000-0000-4000-8000-000000000002",
    }
    response = sdk_auth_api.client.post("/api/analytics/visits", json=payload)
    assert response.status_code == 204, response.content
    assert use_case.record_visit.call_args.kwargs["day"] == datetime.now(UTC).date()
    assert use_case.record_visit.call_args.kwargs["visit"].target_id == "articles"
    use_case.record_visit.reset_mock()
    response = sdk_auth_api.client.post("/api/analytics/visits", json=payload, headers={"dnt": "1"})
    assert response.status_code == 204, response.content
    use_case.record_visit.assert_not_called()
