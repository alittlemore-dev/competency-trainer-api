import pytest
import pytest_asyncio
from verbose_http_exceptions import status

from infra.config.settings import settings
from tests.test_cases import ApiTestCase


class TestContactMeRequestAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.contact_me_id = (await self.container.get_hex_uuid_id_generator()).get_next()
        self.use_case = await self.container.get_contacts_use_case()

    def test_contact_me_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings.app, "contact_requests_enabled", True)
        self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="NAME",
                email="example@mail.ru",
                telegram="@telegram",
                message="MESSAGE",
            ),
        )
        self.use_case.create_contact_me_request.assert_called_once_with(
            form=self.factory.core.contact_me(
                contact_me_id=self.contact_me_id,
                name="NAME",
                email="example@mail.ru",
                telegram="@telegram",
                message="MESSAGE",
            ),
        )

    def test_contact_me_request_returns_204_without_use_case_when_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.app, "contact_requests_enabled", False)
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="NAME",
                email="example@mail.ru",
                telegram="@telegram",
                message="MESSAGE",
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        self.use_case.create_contact_me_request.assert_not_called()

    def test_contact_me_request_is_not_rate_limited_by_backend(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.app, "contact_requests_enabled", True)
        data = self.factory.api.contact_me_request(
            name="NAME",
            email="example@mail.ru",
            telegram="@telegram",
            message="MESSAGE",
        )
        self.api.post_create_contact_me_request(data=data)
        self.api.post_create_contact_me_request(data=data)
        assert self.use_case.create_contact_me_request.call_count == 2

    def test_contact_me_request_no_contact_data(self) -> None:
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name=None,
                email=None,
                telegram=None,
                message="MESSAGE",
            ),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_contact_me_request_requires_name_key(self) -> None:
        data = self.factory.api.contact_me_request(
            name=None,
            email="example@mail.ru",
            telegram=None,
            message="MESSAGE",
        )
        data.pop("name")
        response = self.api.post_create_contact_me_request(data=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.use_case.create_contact_me_request.assert_not_called()

    def test_contact_me_request_requires_telegram_key(self) -> None:
        data = self.factory.api.contact_me_request(
            name=None,
            email="example@mail.ru",
            telegram=None,
            message="MESSAGE",
        )
        data.pop("telegram")
        response = self.api.post_create_contact_me_request(data=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.use_case.create_contact_me_request.assert_not_called()

    def test_contact_me_request_rejects_extra_fields(self) -> None:
        response = self.api.post_create_contact_me_request(
            data={
                **self.factory.api.contact_me_request(
                    name="NAME",
                    email="example@mail.ru",
                    telegram="@telegram",
                    message="MESSAGE",
                ),
                "unexpectedField": "value",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.use_case.create_contact_me_request.assert_not_called()

    def test_contact_me_request_min_length(self) -> None:
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="",
                email="",
                telegram="",
                message="",
            ),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_contact_me_request_rejects_invalid_email(self) -> None:
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="NAME",
                email="not-an-email",
                telegram="@telegram",
                message="MESSAGE",
            ),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.use_case.create_contact_me_request.assert_not_called()

    def test_contact_me_request_max_length(self) -> None:
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="a" * 256,
                email="a" * 256,
                telegram="a" * 267,
                message="a" * 10001,
            ),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_contact_me_request_telegram_max_length_with_special_symbol(self) -> None:
        response = self.api.post_create_contact_me_request(
            data=self.factory.api.contact_me_request(
                name="NAME",
                email="example@mail.ru",
                telegram="a" * 256,
                message="MESSAGE",
            ),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
