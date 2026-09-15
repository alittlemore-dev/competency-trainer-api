from infra.postgresql.query_monitoring import (
    build_slow_query_log_payload,
    is_slow_query,
    normalize_sql_statement,
)


class TestQueryMonitoring:
    def test_normalize_sql_statement_collapses_whitespace(self) -> None:
        assert (
            normalize_sql_statement(
                "SELECT  *\nFROM articles__article_model\tWHERE id = %(id)s",
                200,
            )
            == "SELECT * FROM articles__article_model WHERE id = %(id)s"
        )

    def test_normalize_sql_statement_truncates_long_queries(self) -> None:
        assert normalize_sql_statement("SELECT abcdefghijklmnop", 12) == "SELECT ab..."

    def test_is_slow_query_uses_inclusive_threshold(self) -> None:
        assert is_slow_query(duration_ms=250.0, threshold_ms=250) is True
        assert is_slow_query(duration_ms=249.99, threshold_ms=250) is False

    def test_build_slow_query_payload_excludes_parameters(self) -> None:
        payload = build_slow_query_log_payload(
            statement="SELECT * FROM users WHERE email = %(email)s",
            duration_ms=35.678,
            threshold_ms=25,
            statement_max_length=200,
            executemany=False,
        )

        assert payload == {
            "duration_ms": 35.68,
            "threshold_ms": 25,
            "statement": "SELECT * FROM users WHERE email = %(email)s",
            "executemany": False,
        }
