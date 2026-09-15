from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from performance.query_plans import seed as query_plan_seed
from performance.query_plans.models import (
    REALISTIC_PROFILE,
    QueryPlanProfile,
)


class TestQueryPlanProfileSeed:
    @pytest.mark.parametrize(
        ("seed_function", "expected_count"),
        [
            (query_plan_seed.insert_users, 100),
            (query_plan_seed.insert_auth_sessions, 500),
            (query_plan_seed.insert_article_folders, 20),
            (query_plan_seed.insert_article_analytics, 100_000),
            (query_plan_seed.insert_competency_matrix_resource_links, 24_996),
        ],
    )
    async def test_volume_seed_uses_profile_cardinality(
        self,
        seed_function: Callable[..., Awaitable[None]],
        expected_count: int,
    ) -> None:
        connection = AsyncMock()

        await seed_function(connection=connection, profile=REALISTIC_PROFILE)

        compiled_statements = tuple(
            call.args[0].compile(dialect=postgresql.dialect())
            for call in connection.execute.await_args_list
        )
        assert any(
            "generate_series" in str(compiled) and expected_count in compiled.params.values()
            for compiled in compiled_statements
        )

    async def test_article_seed_uses_explicit_published_and_fts_percentages(self) -> None:
        connection = AsyncMock()

        await query_plan_seed.insert_articles(
            connection=connection,
            profile=REALISTIC_PROFILE,
        )

        statement = connection.execute.await_args.args[0]
        compiled = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            ),
        )
        assert "generate_series(1, 5000)" in compiled
        assert ", 100) < 80" in compiled
        assert ", 100) = 0" in compiled

    async def test_agent_audit_seed_uses_profile_cardinality(self) -> None:
        connection = AsyncMock()

        await query_plan_seed.insert_agent_access_records(
            connection=connection,
            profile=REALISTIC_PROFILE,
        )

        audit_statement = connection.execute.await_args_list[-1].args[0]
        compiled = audit_statement.compile(dialect=postgresql.dialect())
        assert "generate_series" in str(compiled)
        assert REALISTIC_PROFILE.cardinalities.agent_access.audit_events in (
            compiled.params.values()
        )

    async def test_seed_profile_passes_profile_to_every_volume_seed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, QueryPlanProfile]] = []
        volume_seed_names = (
            "insert_users",
            "insert_auth_sessions",
            "insert_tags",
            "insert_article_folders",
            "insert_articles",
            "insert_article_tag_links",
            "insert_article_analytics",
            "insert_article_reactions",
            "insert_resources",
            "insert_competency_matrix_structure",
            "insert_competency_matrix_items",
            "insert_competency_matrix_resource_links",
            "insert_queued_competency_matrix_questions",
            "insert_agent_access_records",
        )

        for seed_name in volume_seed_names:

            async def record_seed(
                *,
                connection: object,
                profile: QueryPlanProfile,
                current_seed_name: str = seed_name,
            ) -> None:
                del connection
                calls.append((current_seed_name, profile))

            monkeypatch.setattr(query_plan_seed, seed_name, record_seed)

        connection = AsyncMock()
        await query_plan_seed.seed_profile(
            connection=connection,
            profile=REALISTIC_PROFILE,
        )

        assert calls == [(name, REALISTIC_PROFILE) for name in volume_seed_names]
