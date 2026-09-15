import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict, cast

from litestar.stores.base import Store
from valkey.asyncio import Valkey

from core.auth.storages import TokenRevocationStorage
from core.auth.types import Token
from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum
from core.cache_tools.schemas import CacheDomainStatus, CacheWarmOperation, CacheWarmSummary
from core.cache_tools.storages import CacheWarmOperationStorage, ResponseCacheStatusStorage
from core.competency_matrix.schemas import QuestionSuggestionQuota
from core.competency_matrix.storages import QuestionSuggestionQuotaStorage
from infra.config.constants import constants

QuotaScript = Callable[..., Awaitable[int]]


class CacheWarmSummaryPayload(TypedDict):
    attempted: int
    written: int
    skipped: int


class CacheWarmOperationPayload(TypedDict):
    operation_id: str
    status: str
    queued_at: str
    summary: CacheWarmSummaryPayload | None


@dataclass(kw_only=True, slots=True, frozen=True)
class ValkeyTokenRevocationStorage(TokenRevocationStorage):
    store: Store

    async def revoke_token(self, token: Token, expires_in_seconds: int) -> None:
        await self.store.set(
            key=self._token_key(token),
            value=b"revoked",
            expires_in=expires_in_seconds,
        )

    async def is_token_revoked(self, token: Token) -> bool:
        return await self.store.exists(key=self._token_key(token))

    def _token_key(self, token: Token) -> str:
        return hashlib.sha256(token).hexdigest()


@dataclass(kw_only=True, slots=True)
class ValkeyQuestionSuggestionQuotaStorage(QuestionSuggestionQuotaStorage):
    valkey: Valkey
    namespace: str
    _consume_quota_script: QuotaScript = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._consume_quota_script = self.valkey.register_script(
            b"""
            local value = redis.call('INCR', KEYS[1])
            if value == 1 then
                redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
            end
            return value
            """,
        )

    async def consume_question_suggestion_quota(
        self,
        *,
        actor_key: str,
        limit: int,
        ttl_seconds: int,
    ) -> QuestionSuggestionQuota:
        consumed = await self._consume_quota_script(
            keys=[self._quota_key(actor_key=actor_key)],
            args=[ttl_seconds],
        )
        return QuestionSuggestionQuota(
            allowed=consumed <= limit,
            remaining=max(limit - consumed, 0),
        )

    def _quota_key(self, *, actor_key: str) -> str:
        return f"{self.namespace}:{actor_key}"


@dataclass(kw_only=True, slots=True, frozen=True)
class ValkeyResponseCacheStatusStorage(ResponseCacheStatusStorage):
    valkey: Valkey
    namespaces: dict[CacheDomainEnum, str]
    scan_batch_size: int

    async def get_domain_status(self, *, domain: CacheDomainEnum) -> CacheDomainStatus:
        cursor = 0
        seen_keys: set[bytes] = set()
        key_count = 0
        minimum_remaining_ttl_seconds: int | None = None
        non_expiring_key_count = 0
        while True:
            cursor, keys = await self.valkey.scan(
                cursor=cursor,
                match=f"{self.namespaces[domain]}:*",
                count=self.scan_batch_size,
            )
            new_keys = [key for key in keys if key not in seen_keys]
            seen_keys.update(new_keys)
            if new_keys:
                pipeline = self.valkey.pipeline(transaction=False)
                for key in new_keys:
                    pipeline.ttl(key)
                ttl_values = cast("list[int]", await pipeline.execute())
                for ttl_seconds in ttl_values:
                    if ttl_seconds == constants.valkey.missing_ttl_seconds:
                        continue
                    key_count += 1
                    if ttl_seconds == constants.valkey.non_expiring_ttl_seconds:
                        non_expiring_key_count += 1
                    elif (
                        minimum_remaining_ttl_seconds is None
                        or ttl_seconds < minimum_remaining_ttl_seconds
                    ):
                        minimum_remaining_ttl_seconds = ttl_seconds
            if cursor == 0:
                break
        return CacheDomainStatus(
            domain=domain,
            key_count=key_count,
            minimum_remaining_ttl_seconds=minimum_remaining_ttl_seconds,
            non_expiring_key_count=non_expiring_key_count,
        )


@dataclass(kw_only=True, slots=True, frozen=True)
class ValkeyCacheWarmOperationStorage(CacheWarmOperationStorage):
    store: Store
    expires_in_seconds: int

    async def create(self, *, operation: CacheWarmOperation) -> None:
        await self.store.set(
            key=self.operation_key(operation_id=operation.operation_id),
            value=self.serialize(operation=operation),
            expires_in=self.expires_in_seconds,
        )
        await self.store.set(
            key=constants.taskiq.cache_warm_latest_operation_key,
            value=operation.operation_id,
            expires_in=self.expires_in_seconds,
        )

    async def update(self, *, operation: CacheWarmOperation) -> None:
        await self.store.set(
            key=self.operation_key(operation_id=operation.operation_id),
            value=self.serialize(operation=operation),
            expires_in=self.expires_in_seconds,
        )
        await self.store.get(
            key=constants.taskiq.cache_warm_latest_operation_key,
            renew_for=self.expires_in_seconds,
        )

    async def get(self, *, operation_id: str) -> CacheWarmOperation | None:
        value = await self.store.get(key=self.operation_key(operation_id=operation_id))
        if value is None:
            return None
        return self.deserialize(value=value)

    async def get_latest(self) -> CacheWarmOperation | None:
        operation_id = await self.store.get(
            key=constants.taskiq.cache_warm_latest_operation_key,
        )
        if operation_id is None:
            return None
        return await self.get(operation_id=operation_id.decode())

    def operation_key(self, *, operation_id: str) -> str:
        return f"{constants.taskiq.cache_warm_operation_key_prefix}:{operation_id}"

    def serialize(self, *, operation: CacheWarmOperation) -> bytes:
        payload = CacheWarmOperationPayload(
            operation_id=operation.operation_id,
            status=operation.status.value,
            queued_at=operation.queued_at.isoformat(),
            summary=(
                CacheWarmSummaryPayload(
                    attempted=operation.summary.attempted,
                    written=operation.summary.written,
                    skipped=operation.summary.skipped,
                )
                if operation.summary is not None
                else None
            ),
        )
        return json.dumps(payload, separators=(",", ":")).encode()

    def deserialize(self, *, value: bytes) -> CacheWarmOperation:
        payload = cast("CacheWarmOperationPayload", json.loads(value))
        summary_payload = payload["summary"]
        return CacheWarmOperation(
            operation_id=payload["operation_id"],
            status=CacheWarmOperationStatusEnum(payload["status"]),
            queued_at=datetime.fromisoformat(payload["queued_at"]),
            summary=(
                CacheWarmSummary(
                    attempted=summary_payload["attempted"],
                    written=summary_payload["written"],
                    skipped=summary_payload["skipped"],
                )
                if summary_payload is not None
                else None
            ),
        )
