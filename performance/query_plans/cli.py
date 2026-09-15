import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from performance.query_plans import run_query_plan_profile
from performance.query_plans.models import REALISTIC_PROFILE, STRESS_PROFILE, CliArgs


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="Seed PostgreSQL and EXPLAIN ANALYZE real SQLAlchemy search queries.",
    )
    parser.add_argument(
        "--profile",
        choices=(REALISTIC_PROFILE.name, STRESS_PROFILE.name),
        required=True,
    )
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--fail-on-finding", action="store_true")
    parser.add_argument("--allow-non-test-db", action="store_true")
    namespace = parser.parse_args(argv)
    return CliArgs(
        profile=cast("str", namespace.profile),
        report_dir=Path(cast("str", namespace.report_dir)),
        fail_on_finding=cast("bool", namespace.fail_on_finding),
        allow_non_test_db=cast("bool", namespace.allow_non_test_db),
    )


def main() -> None:
    raise SystemExit(asyncio.run(run_query_plan_profile(parse_args())))
