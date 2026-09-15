# Backend Testing Instructions

These rules apply to backend tests under `tests/**/*.py`.

## Philosophy

Choose the test boundary required by the behavior. Keep isolated branch logic in unit tests;
use real PostgreSQL and middleware where transaction, concurrency, query, or HTTP behavior depends
on them. Follow the repository root verification policy.

## Unit vs. Integration Tests

| Type | Definition | Directory |
|---|---|---|
| Unit | Single layer in isolation. Uses mock storages/providers. | `tests/unit/` |
| DB integration | Storage and core behavior against real PostgreSQL; HTTP is not required. | `tests/integration/` |
| HTTP full-stack integration | Selected HTTP paths through real middleware, use cases, appropriate real providers, and PostgreSQL. | `tests/integration/` |
| Migration | Alembic revision upgrade/downgrade behavior against real PostgreSQL. | `tests/migrations/` |

## Unit Tests

- Isolate the layer under test; do not use a real database or external services. Use existing
  mock providers and spec-constrained storage mocks from neighboring tests.

## Integration Tests

- Use DB integration tests for storage, SQL, transaction, and concurrency behavior that requires real
  PostgreSQL; these tests do not need to traverse HTTP or instantiate unrelated providers.
- Use selected HTTP full-stack integration tests when behavior depends on the real handler,
  middleware, dependency wiring, use case, and PostgreSQL path. Use the appropriate real Dishka
  providers for the stack under test rather than replacing that path with mocks.
- Cover relevant success, failure, security, transaction, and concurrency contracts at the boundary
  that can prove them. Avoid duplicating isolated unit branches through the full HTTP stack.
- Real PostgreSQL test DB (`competency_trainer_database_test`) — tests under `tests/integration/`
  are auto-migrated to `heads` via their package conftest.
- Inherit `StorageTestCase` for DB assertion helpers; session auto-rollbacks after each test.
- Alembic migration tests live outside `integration/` under `tests/migrations/`, with one
  file per revision named `test_<revision>.py`; each file should cover upgrade and downgrade behavior
  and explicitly call migration helpers for the revision under test.

## Migration Tests

- Prefer testing migrations against populated tables affected by the revision. For a migration that
  changes an existing table, migrate to the revision immediately before the one under test, insert
  representative rows into that table, then run the target migration and assert the data/schema
  result.
- Do not import application ORM models in migration tests. Use only SQLAlchemy Core tables,
  columns, expressions, and query builder constructs because later revisions may remove or reshape
  ORM models that older migration tests still need to exercise.
- Use SQLAlchemy Core tables, expressions, and query builder constructs in migration tests by
  default. A narrow, documented raw-SQL exception is allowed only when a test must exercise
  PostgreSQL DDL or an expression that cannot be represented by the typed operations available in
  the project. Raw DML remains prohibited when SQLAlchemy Core can express the operation.

## Commands

From the project root::

```bash
make test-unit           # unit tests only (fast, run often)
make test-integration    # integration + migration tests; starts/reuses test DB automatically
make tests               # all tests
make tests-coverage      # all + coverage report
```

From the repository root:

```bash
make tests-fast          # backend unit tests; no backend test PostgreSQL
make tests-compose       # starts/reuses test PostgreSQL, runs tests, then cleans up owned services
make test-env-up         # start isolated test PostgreSQL manually
make test-env-down       # stop isolated test PostgreSQL and remove its data
```

Backend pytest parallelism is explicit. Do not use `pytest-xdist -n auto`: the Make-backed test
script computes physical CPU cores and passes `-n <workers>` itself. Override it only with
`BACKEND_PYTEST_WORKERS`: `0` and `1` force serial execution, while any value greater than `1`
forces that exact worker count.

`make test-unit` runs only `tests/unit/` and must not require a test database. Integration
pytest workers clone a migrated run-scoped template database into isolated PostgreSQL databases
named from the base database plus the xdist worker suffix, such as `competency_trainer_database_test_gw0`.
Alembic migration tests must stay serial because they exercise upgrade/downgrade behavior against
the shared base schema.

## Existing test support

- Use `tests/test_cases.py`: `TestCase` for factories/assertions/collections,
  `ContainerTestCase` for Dishka, `ApiTestCase` for HTTP helpers, and `StorageTestCase` for database
  assertions and automatic rollback. Follow adjacent tests for their public helper APIs.
- Reuse `tests/unit/mocks/providers/` and the plain-Python factories under
  `tests/helpers/factories/` (`CoreFactoryHelper` and `ApiFactoryHelper`; no Mimesis).
  Create domain objects through `self.factory.core.*` when covered; defaults are allowed in tests.
- Put reusable endpoint helpers in `tests/helpers/api.py`, HTTP assertions in
  `helpers/assertions.py`, and useful repeated collection projections in `helpers/collections.py`.
  Keep scenario-specific payload assertions and setup visible in the test. Add factory builders
  only for setups reused across tests.
- Test generated schema, migration/data results, security boundaries, query behavior, and observable
  API/core contracts. Do not duplicate ORM declarations, trivial converters, source text, package
  versions, lockfiles, or exact command strings as tests.
- Cover changed critical behavior; repository-wide numeric gates belong in test/CI configuration.
  Ordinary tests follow neighboring feature/component naming; migration tests stay
  `test_<revision>.py` and independent of current ORM models.
