from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from infra.config.initializers import init_sentry
from infra.config.settings import settings

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint


class OfflineSentryTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)


def fail_with_sensitive_asgi_scope(*, credential: str) -> None:
    scope = {"headers": [(b"authorization", f"Bearer {credential}".encode())]}
    assert scope["headers"]
    message = "Request failed safely"
    raise RuntimeError(message)


@pytest.mark.parametrize("event_kind", ["exception", "transaction"])
def test_serialized_sentry_events_exclude_credential_locals_and_request_data(
    event_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.sentry, "use", True)
    with patch("infra.config.initializers.sentry_sdk.init") as initialize:
        init_sentry()
    options = dict(initialize.call_args.kwargs)
    transport = OfflineSentryTransport()
    options.update(
        dsn="https://public@example.invalid/1",
        transport=transport,
        default_integrations=False,
        integrations=[],
    )
    credential = uuid4().hex
    request_secret = uuid4().hex

    def add_sensitive_request(event: Event, _hint: Hint) -> Event:
        event["request"] = {
            "url": "https://site.example/api/admin/competency-matrix/items",
            "headers": {"Authorization": f"Bearer {credential}"},
            "cookies": {"session": request_secret},
            "data": {"content": request_secret},
            "query_string": f"token={request_secret}",
        }
        return event

    client = sentry_sdk.Client(**options)
    try:
        with sentry_sdk.isolation_scope() as scope:
            scope.set_client(client)
            scope.add_event_processor(add_sensitive_request)
            if event_kind == "exception":
                with pytest.raises(RuntimeError) as error:
                    fail_with_sensitive_asgi_scope(credential=credential)
                assert sentry_sdk.capture_exception(error.value) is not None
            else:
                with sentry_sdk.start_transaction(name="privacy-test", op="http.server"):
                    pass
    finally:
        client.close()

    assert len(transport.envelopes) == 1
    envelope = transport.envelopes[0]
    serialized = envelope.serialize().decode()
    assert credential not in serialized
    assert request_secret not in serialized
    event = envelope.get_event() if event_kind == "exception" else envelope.get_transaction_event()
    assert event is not None
    assert event["request"] == {
        "url": "https://site.example/api/admin/competency-matrix/items",
    }
    if event_kind == "exception":
        assert event["exception"]["values"][0]["type"] == "RuntimeError"
