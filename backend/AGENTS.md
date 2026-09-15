# Backend Instructions

These rules apply to all backend-owned code, configuration, tooling, documentation, and supporting
files under `backend/`. Keep shared cross-project configuration and common infrastructure outside
`backend/`.

## Code Style

- Use `backend/pyproject.toml` as the source for formatting, lint, and typing configuration.
- No docstrings unless interface is non-obvious from types
- Comments: only for non-obvious WHY, never WHAT
- No Python class name may start with a leading underscore anywhere under `backend/`, including
  production code, tests, migrations, scripts, and performance tooling; there are no exceptions.
  Give every class a clear public name and control module exports through import/export boundaries
  rather than private class naming.
- Keep environment/configuration values, shared operational limits, and configurable policy values
  in `backend/src/infra/config/constants.py`. Domain invariants, parser-specific rules, adapter-local
  mappings, and other implementation constants belong with the domain, parser, or adapter that owns
  them. Core code must receive infrastructure-owned configuration through schemas, constructor
  parameters, or IOC wiring, while infra and entrypoint code may import `constants` directly when
  that layer owns the wiring.

## Layers

| Layer | Path | Responsibility |
|---|---|---|
| Domain | `backend/src/core/` | Business logic. Pure Python only. |
| Persistence | `backend/src/infra/postgresql/` | SQLAlchemy models + concrete storage implementations |
| Interface | `backend/src/entrypoints/litestar/` | HTTP handlers, API endpoints, auth middleware |
| DI | `backend/src/infra/ioc/` | Dishka providers. Wiring only, no logic |
| Config | `backend/src/infra/config/` | Pydantic settings, logging setup |
| File storage | `backend/src/infra/s3/` | S3-compatible files adapter for MinIO |

## Tooling Boundaries

- Performance and test tooling may import reusable application contracts from `backend/src`, such
  as enums, schemas, factories, and public helpers, but tooling-specific infrastructure must live
  with that tooling. Do not create performance-only or test-only support modules under
  `backend/src`; keep performance support under `backend/performance/` and test support under
  `backend/tests/`.

## Operation Boundaries

- Do not model entity mutation methods as `upsert` when the behavior can create, update,
  delete, or otherwise mutate different state. Use explicit operation-specific names and methods
  such as `create_*`, `update_*`, `delete_*`, `publish_*`, or `set_*` so callers cannot
  accidentally trigger broader behavior than intended.

## Business Logic Boundaries

- Business-operation orchestration and flows that coordinate multiple storages belong in domain use
  cases under `backend/src/core/**/use_cases.py`. Invariants and behavior owned by one entity or
  value object belong on that domain object. Shared cross-use-case domain behavior belongs in an
  explicit core domain service.
- When an existing use-case operation already represents the business action, reuse it with
  explicit parameters that model transport/auth/quota differences instead of adding a parallel
  use-case method for the same action. Do not use sentinel values such as arbitrarily large quotas;
  make the variation explicit in the parameter contract.
- API controllers, Litestar handlers, API schemas, Dishka providers, storages, ORM models, settings,
  event dispatchers, and infrastructure adapters must not own business decisions. They may validate
  transport shape, map data, wire dependencies, persist/load data, or call a use case.
- Request-level access checks and input checks that can be decided before entering a use case should
  live at the Litestar boundary, preferably as guards or `Provide` dependencies. Do not hide those
  checks in controller helper functions.
- Do not add private module-level helper functions in backend source to hold business behavior.
  Put the behavior on the real owning class or use case instead.
- Do not create classes that exist only to wrap one or more `@classmethod` helpers. A class must
  represent a real domain concept, interface, adapter, provider, guard, schema, model, or service.
- Put reusable domain parsers in the domain `parsers.py`, reader interfaces in `readers.py`,
  parser/request DTOs and rule objects in `schemas.py`, and parser/domain errors in
  `exceptions.py`. Do not name domain files after one narrow feature when an existing standard
  file type fits the object.
- Top-level functions are acceptable when the framework or tool naturally requires them or when a
  callable class would add ceremony without improving ownership: app factories, Litestar lifespan
  hooks, CLI commands, Alembic migration functions, and small pure infrastructure entrypoints.
- When choosing between a function and a method, prefer the shape that expresses real ownership.
  Do not move code into a class solely to satisfy a stylistic ban on functions.
- Prefer moving meaningful multi-parameter object creation into methods on the object that owns
  that creation logic, or into the owning use case when the object is an aggregate/read model.
  Do not extract creation solely for tiny objects with too few fields to justify the extra method.
- Storage adapters may filter, group, paginate, count, and otherwise aggregate data when those
  operations are part of the database query shape. They should return persisted entities or narrow
  row/query results. Product-facing composition, cross-storage assembly, and business decisions must
  remain in core use cases or on the owning core object. Simple containers such as
  `Tags(values=...)` and `ExternalResources(values=...)` may remain at storage boundaries when they
  only wrap loaded values.

## HTTP and Schemas

- Controllers must receive dependencies through `FromDishka[...]`, typed as the concrete use case
  class registered in Dishka.
- Endpoint/controller modules must not define `@staticmethod`, `@classmethod`, or private helper
  methods for request-derived values or parameter assembly when a Litestar `Provide` dependency can
  own that logic. Put those dependencies in a neighboring `dependencies.py` module.
- Assemble query/path/header/cookie parameter objects in neighboring `dependencies.py` Litestar
  `Provide` dependencies when this keeps handlers focused on their HTTP contract.
- Public discovery response assembly, such as sitemap URL collection, sitemap XML rendering, and
  robots.txt rendering, must not live in `endpoints.py` controller modules. Keep it in a neighboring
  `backend/src/entrypoints/litestar/**` module owned by the HTTP entrypoint layer, not in `core`.
- API schemas must inherit from the shared schema bases and map explicitly between API, ORM, and
  core representations. Use `to_domain_schema` for conversion to the same core concept and
  `from_domain_schema` for conversion from it when the method signature identifies the exact
  source/target type. Use a specific semantic conversion name only when the conversion changes the
  concept, such as attached resource -> plain external resource.
- Do not use `cast("Self", ...)` to suppress classmethod return-type errors. Use an accurately typed
  constructor or an explicit concrete return type.
- Do not pass Pydantic API schemas, SQLAlchemy models, or Litestar types into the core layer.

## Response Caching

- Cache API GET responses only through the domain response cache helpers in
  `backend/src/entrypoints/litestar/response_cache.py`. Use a `ResponseCacheDomain`
  and its `cache_key_builder` property so keys are domain-prefixed and routed to the
  matching Valkey namespace; do not add ad hoc cache key builders or write directly to a
  shared response-cache namespace.
- Safe, stable GET handlers may use Litestar response caching with explicit cache metadata.
  Keep user-implicit, privileged statistics, analytics, file-management, account/session, and other
  request-side-effect or user-specific responses uncached unless a new design explicitly
  makes their cache key and invalidation rules safe.
- If a cached GET depends on auth-sensitive query parameters, enforce the access check with a
  Litestar guard or another pre-cache boundary check. Do not rely only on controller body checks
  because Litestar can return a cached response before executing the handler body.
- Mutating handlers that change cached domain content must call
  `invalidate_response_cache_domain_for_mutation(...)` only after the use case succeeds. The helper
  must not invalidate before commit; it registers one post-commit action that first invalidates the
  domain and then enqueues its TaskIQ warm. The action must run only after a successful database
  commit, never after rollback or a failed commit. Do not invalidate or enqueue on
  validation/auth/use-case failures, and do not invalidate content caches for analytics-only
  changes when analytics are served from separate uncached endpoints.
- Response-cache warmers live under `backend/src/entrypoints/taskiq/cache_warm/` and must write
  Litestar-compatible msgpack-encoded ASGI response messages through `ResponseCacheDomainStore`.
  Do not write raw JSON response-cache payloads.

## Background Tasks

- TaskIQ entrypoints live under `backend/src/entrypoints/taskiq/`.
- Keep `backend/src/entrypoints/taskiq/broker.py` as the shared broker and
  `backend/src/entrypoints/taskiq/worker.py` as the worker/scheduler registry entrypoint.
- Put domain task wrappers in domain packages such as
  `backend/src/entrypoints/taskiq/cache_warm/tasks.py`; do not collect unrelated tasks in a
  top-level `tasks.py`.
- Background tasks are internal worker/scheduler processes, not HTTP handlers.
- Run exactly one TaskIQ scheduler process in deployment. Scale TaskIQ workers when more background
  execution capacity is needed.
- TaskIQ result metadata is operational and ephemeral in Valkey unless a future durable task
  history/auditing design explicitly chooses another backend.

## Agent Access Boundaries

- Production agent transport is the seven-route Agent contour mounted in the main Litestar
  application behind the separate VPN-bound nginx mTLS listener. Its handlers and schemas live in
  the common
  `backend/src/entrypoints/litestar/api/agent_access/` layout, with authentication/audit middleware
  and composition helpers in the common Litestar packages. Keep Agent authentication, exception
  mapping, request limits, transaction rollback, and audit behavior scoped to that router/path, and
  exclude it from human PASETO authentication and OpenAPI. nginx may forward only five business
  operations plus two certificate-rotation operations through the exact mTLS allowlist. The public
  listener must return `404` for the internal path and strip caller-supplied certificate headers.
  Do not add a separate Agent process/socket, remote MCP endpoint, human PASETO authentication,
  generic HTTP proxying/CRUD, SQL, shell, publishing, deletion, structure mutation, or server-side
  URL fetch.
- The local stdio MCP bridge under `backend/src/entrypoints/agent_bridge/` exposes only
  `claim_next_matrix_question`, `get_matrix_authoring_context`, `search_matrix_resources`,
  `save_matrix_question_draft`, and `release_matrix_question_claim`. Keep only MCP schemas, tool
  registration/mapping, and the sanitized exception boundary there; `backend/src/agent_bridge.py`
  is the executable launcher. Business contracts and bridge/rotation orchestration belong in
  `core/agent_access`, while concrete HTTP/mTLS and crypto/files adapters belong in `infra`.
- Enforce distinct client/certificate identity and explicit scopes on every business request. The
  Agent contour uses the main settings, Dishka container, request transaction/session factory,
  database role, process, secrets, and availability boundary. The closed REST surface, transport
  validation, core rules, and operation-specific storages prevent publish/delete/general SQL
  through the supported contract, but backend compromise, SQL injection, or erroneous arbitrary
  SQL has the main backend role's database blast radius and can expose unrelated process secrets.
  Keep owner-only registration, revocation, and privacy-safe audit under the human
  `/api/admin/agent-clients` contour.
- Trust the forwarded certificate only on the VPN-bound nginx mTLS-to-backend contour. Keep the
  backend unreachable from untrusted networks and strip caller-supplied certificate headers on the
  public listener. A compromised service that can reach the backend on the private application
  network can forge that header; network isolation and the nginx trust boundary are required
  controls. Never store client private keys, log prompts/full authored content, or omit
  action/digest audits. Queue, existing authored content, tool output, and web text are untrusted
  data.
- Claims stay two hours and completion stays atomic, server-forced `Draft`, complete in RU/EN, and
  limited to one to three existing-ID or new-HTTPS resources. Store resource URLs without fetching.
- Keep settings in `infra/config`, infrastructure adapters in their owning infra packages, and
  dependency assembly in Dishka providers/composition roots. Related Agent policy primitives must
  be mapped into typed core policy objects rather than passed as constructor fan-out. Use existing
  generator contracts and explicit current-time operation inputs; do not add callable factories such
  as `rotation_id_factory`, `current_datetime_factory`, or `now_factory` for Agent Access. Handlers
  and bridge transport must not hand-build engines, storages, clients, or use cases. Use the main
  application settings/container/session factory; do not add an Agent-specific app factory,
  settings/database loader, database engine/session factory, process, or Unix socket.
- Client P-256 keys remain local with mode `0600`. Desktop credentials use recoverable two-phase
  rotation: persist pending state, reuse the rotation ID/CSR after lost responses, switch
  atomically, confirm with the replacement, and only then revoke/remove the predecessor. External
  credential mode never rotates automatically.

## I18n

- The backend i18n catalog is the source of truth for UI interface strings and enum labels.
  Database/content localisation is separate from the UI catalog.
- Articles, article tags, article folders, and competency matrix content localise with required fixed fields in their
  owning tables: article `title_ru`, `title_en`, `content_ru`, `content_en`; article folder
  `name_ru`, `name_en`; tag `name_ru`, `name_en`; plus competency matrix item `question_*`, `answer_*`,
  `interview_answer_explanation_*`, matrix structure `name_ru`/`name_en` on sheet, section, and
  subsection tables, resource `name_*`, and attachment `context_*` fields.
  Competency matrix sheets must use a stable language-neutral `key`/`sheetKey` identifier, and
  questions must reference the normalized structure through a required `subsection_id`.
  Do not add generic translation tables, production defaults, or fallback language behavior unless
  an explicit design change asks for them.
- Localized read-facing core entities and read models should carry language-neutral projected fields
  such as `title`, `content`, `folder`, `name`, and localized matrix text, selected for the requested
  `LanguageEnum` before those objects are constructed. Write and persistence contracts may retain
  explicit RU/EN fields when both translations are required. Do not require canonical RU/EN fields
  on every read-facing core entity.
- Article SEO metadata belongs to the article contract, not to a generic translation table.
  Keep the explicit nullable fields `seo_title_ru`, `seo_title_en`, `seo_description_ru`,
  `seo_description_en`, `cover_image_file_id`, `cover_image_alt_ru`, and `cover_image_alt_en` on
  article write/domain/storage contracts. `cover_image_url` is computed for read responses from the
  managed `FileModel` metadata. Article create/update API payloads must require the `metadata`
  object itself while allowing individual metadata fields to be null, with no production defaults.
- Read/write APIs that expose localized article, article-folder, tag, or competency matrix content
  must use the backend language enum and require explicit `LanguageEnum`/`language` selection where
  localized values are returned.
- Supported UI languages must be modeled with a backend enum. Do not accept arbitrary language
  strings in production API/settings code.
- The default UI language must be configured explicitly through the required
  `I18N_DEFAULT_LANGUAGE` environment setting; do not add production defaults for it.
- Keep the available-languages endpoint and bundle endpoint consistent with the enum and catalog,
  and cover new languages/keys with catalog parity tests.
- Content localisation beyond articles, article tags, article folders, and competency matrix
  content remains future work until explicitly designed.

## Article Analytics

- Keep article analytics privacy-safe unless an explicit design change says otherwise. Do not store
  raw IP addresses, raw user-agent strings, raw referrers, analytics cookies, or third-party
  analytics identifiers. Use referrers only for immediate coarse source classification, and store
  only article-scoped derived identifiers for anonymous reactions.

## Persistence

- SQLAlchemy models and database storages live only under `backend/src/infra/postgresql/`.
- Database storages return domain schemas, not ORM models.
- Storages may `flush`, but must not `commit`; transaction ownership belongs to the DI/session provider.
- Every DB model change must include a matching Alembic migration.

## Performance

- For backend changes that can realistically affect PostgreSQL query shape, storage access patterns,
  indexes, migrations, or data-volume behavior, run `make query-plans-realistic` before the first
  implementation change and again after the task, then compare the generated reports.
- Skip the before/after query-plan workflow for changes outside the PostgreSQL performance contour,
  and for narrow documentation, formatting, test-only, typing-only, naming-only, or localized
  mechanical changes. If a pre-change run cannot be performed because the task starts from a broken
  state, record that in the final response and compare against the nearest available baseline/report.

## Dependency Injection

- Dishka providers are wiring only: no business logic, DB queries, or external side effects.
- Use `Scope.APP` only for stateless singleton-safe dependencies; use `Scope.REQUEST` for sessions, storages, and use cases.
