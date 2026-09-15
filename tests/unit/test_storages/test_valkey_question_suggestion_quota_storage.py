from infra.valkey.storages import ValkeyQuestionSuggestionQuotaStorage


class FakeScript:
    def __init__(self, value: int) -> None:
        self.value = value
        self.calls: list[tuple[list[str], list[int]]] = []

    async def __call__(self, *, keys: list[str], args: list[int]) -> int:
        self.calls.append((keys, args))
        return self.value


class FakeValkey:
    def __init__(self, script_value: int) -> None:
        self.script = FakeScript(script_value)
        self.registered_scripts: list[bytes] = []

    def register_script(self, script: bytes) -> FakeScript:
        self.registered_scripts.append(script)
        return self.script


class TestValkeyQuestionSuggestionQuotaStorage:
    async def test_consumes_daily_quota_with_atomic_script(self) -> None:
        client = FakeValkey(script_value=3)
        storage = ValkeyQuestionSuggestionQuotaStorage(
            valkey=client,  # type: ignore[arg-type]
            namespace="MATRIX_QUESTION_SUGGESTIONS",
        )

        quota = await storage.consume_question_suggestion_quota(
            actor_key="hashed-actor",
            limit=10,
            ttl_seconds=86_400,
        )

        assert quota.allowed is True
        assert quota.remaining == 7
        assert client.script.calls == [
            (["MATRIX_QUESTION_SUGGESTIONS:hashed-actor"], [86_400]),
        ]
        assert b"INCR" in client.registered_scripts[0]
        assert b"EXPIRE" in client.registered_scripts[0]

    async def test_reports_exhausted_quota(self) -> None:
        client = FakeValkey(script_value=11)
        storage = ValkeyQuestionSuggestionQuotaStorage(
            valkey=client,  # type: ignore[arg-type]
            namespace="MATRIX_QUESTION_SUGGESTIONS",
        )

        quota = await storage.consume_question_suggestion_quota(
            actor_key="hashed-actor",
            limit=10,
            ttl_seconds=86_400,
        )

        assert quota.allowed is False
        assert quota.remaining == 0
