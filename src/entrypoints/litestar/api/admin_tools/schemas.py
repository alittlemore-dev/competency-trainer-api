from datetime import datetime
from typing import Annotated

from pydantic import Field

from core.auth.schemas import AuthSessionCleanupResult, AuthSessionCleanupStatus
from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum
from core.cache_tools.schemas import (
    CacheDomainStatus,
    CacheToolsStatus,
    CacheWarmOperation,
    CacheWarmSummary,
)
from entrypoints.litestar.api.schemas import CamelCaseSchema


class AuthSessionsStatusResponseSchema(CamelCaseSchema):
    expired_count: Annotated[int, Field(title="Expired session count")]
    expiring_soon_count: Annotated[int, Field(title="Expiring soon session count")]
    expiring_soon_days: Annotated[int, Field(title="Expiring soon window in days")]
    scheduled_prune_interval_seconds: Annotated[
        int,
        Field(title="Scheduled prune interval in seconds"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AuthSessionCleanupStatus,
    ) -> AuthSessionsStatusResponseSchema:
        return cls.model_construct(
            expired_count=schema.expired_count,
            expiring_soon_count=schema.expiring_soon_count,
            expiring_soon_days=schema.expiring_soon_days,
            scheduled_prune_interval_seconds=schema.scheduled_prune_interval_seconds,
        )


class AuthSessionsPruneResponseSchema(CamelCaseSchema):
    deleted_count: Annotated[int, Field(title="Deleted session count")]
    expired_count: Annotated[int, Field(title="Expired session count")]
    expiring_soon_count: Annotated[int, Field(title="Expiring soon session count")]
    expiring_soon_days: Annotated[int, Field(title="Expiring soon window in days")]
    scheduled_prune_interval_seconds: Annotated[
        int,
        Field(title="Scheduled prune interval in seconds"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AuthSessionCleanupResult,
    ) -> AuthSessionsPruneResponseSchema:
        return cls.model_construct(
            deleted_count=schema.deleted_count,
            expired_count=schema.expired_count,
            expiring_soon_count=schema.expiring_soon_count,
            expiring_soon_days=schema.expiring_soon_days,
            scheduled_prune_interval_seconds=schema.scheduled_prune_interval_seconds,
        )


class CacheWarmSummaryResponseSchema(CamelCaseSchema):
    attempted: Annotated[int, Field(title="Attempted cache targets")]
    written: Annotated[int, Field(title="Written cache targets")]
    skipped: Annotated[int, Field(title="Skipped cache targets")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CacheWarmSummary,
    ) -> CacheWarmSummaryResponseSchema:
        return cls.model_construct(
            attempted=schema.attempted,
            written=schema.written,
            skipped=schema.skipped,
        )


class CacheWarmOperationResponseSchema(CamelCaseSchema):
    operation_id: Annotated[str, Field(title="Cache warm operation ID")]
    status: Annotated[CacheWarmOperationStatusEnum, Field(title="Cache warm status")]
    queued_at: Annotated[datetime, Field(title="Queue timestamp")]
    summary: Annotated[
        CacheWarmSummaryResponseSchema | None,
        Field(title="Completed cache warm summary"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CacheWarmOperation,
    ) -> CacheWarmOperationResponseSchema:
        return cls.model_construct(
            operation_id=schema.operation_id,
            status=schema.status,
            queued_at=schema.queued_at,
            summary=(
                CacheWarmSummaryResponseSchema.from_domain_schema(schema=schema.summary)
                if schema.summary is not None
                else None
            ),
        )


class CacheDomainStatusResponseSchema(CamelCaseSchema):
    domain: Annotated[CacheDomainEnum, Field(title="Cache domain")]
    key_count: Annotated[int, Field(title="Current key count")]
    minimum_remaining_ttl_seconds: Annotated[
        int | None,
        Field(title="Minimum remaining key TTL in seconds"),
    ]
    non_expiring_key_count: Annotated[int, Field(title="Non-expiring key count")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CacheDomainStatus,
    ) -> CacheDomainStatusResponseSchema:
        return cls.model_construct(
            domain=schema.domain,
            key_count=schema.key_count,
            minimum_remaining_ttl_seconds=schema.minimum_remaining_ttl_seconds,
            non_expiring_key_count=schema.non_expiring_key_count,
        )


class CacheStatusResponseSchema(CamelCaseSchema):
    enabled: Annotated[bool, Field(title="Response cache enabled")]
    configured_ttl_seconds: Annotated[int, Field(title="Configured response cache TTL")]
    scheduled_warm_interval_seconds: Annotated[
        int,
        Field(title="Scheduled cache warm interval in seconds"),
    ]
    domains: Annotated[list[CacheDomainStatusResponseSchema], Field(title="Cache domains")]
    last_manual_warm_operation: Annotated[
        CacheWarmOperationResponseSchema | None,
        Field(title="Last manual cache warm operation"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CacheToolsStatus,
    ) -> CacheStatusResponseSchema:
        return cls.model_construct(
            enabled=schema.enabled,
            configured_ttl_seconds=schema.configured_ttl_seconds,
            scheduled_warm_interval_seconds=schema.scheduled_warm_interval_seconds,
            domains=[
                CacheDomainStatusResponseSchema.from_domain_schema(schema=domain)
                for domain in schema.domains
            ],
            last_manual_warm_operation=(
                CacheWarmOperationResponseSchema.from_domain_schema(
                    schema=schema.last_manual_warm_operation,
                )
                if schema.last_manual_warm_operation is not None
                else None
            ),
        )
