# AGENTS.md

## Project

Portfolio and articles site

## Stack

- Runtime: Python 3.14, uv, Granian ASGI server
- Framework: Litestar 2.24+
- DB: PostgreSQL 18.4 + SQLAlchemy 2.0 async + Alembic
- DI: Dishka
- Cache: Valkey
- Background tasks: TaskIQ + taskiq-redis over Valkey
- File storage: MinIO through an aiobotocore S3-compatible adapter
- Human identity boundary: neutral `core.identity` contracts; authentication is owned outside this service
- Logging: structlog + ECS logging + Sentry SDK
- Scope: backend service published as a container image for the shared platform runtime

## General rules

- Use current official documentation when library/API behavior, setup, or configuration is
  uncertain or version-sensitive; cite external sources used.
- Do not perform any git action that changes repository state unless I explicitly ask for it. This includes `git add`, `git commit`, `git push`, `git stash`, branch creation, branch switching, rebasing, merging, resetting, checking out files, and similar mutating operations.
- When updating `docs/TODO.md`, do not modify the content or scope of an existing TODO item. Record
  newly discovered follow-up work as a separate TODO item instead of expanding an existing one. Do
  not add the current task to the roadmap merely because it was requested; add only unfinished or
  explicitly requested follow-up work. When an existing TODO item has been fully implemented, change
  its checkbox from `[ ]` to `[x]`; updating completion status is not a content modification and must
  not be skipped.
- Scale planning to the task: use a concise plan for multi-step or cross-cutting work. Requested
  changes include necessary reversible local edits and task-relevant verification; do not stop for
  a separate workflow approval when scope and authorization are already clear.
- Keep task plans in the conversation unless a durable handoff requires a file or the user asks
  for one. Do not create workflow artifacts solely to satisfy a skill.
- Verify changed behavior with focused tests and use a reproducing regression test for bug fixes
  where practical. Choose test order and scope to fit the change; do not require TDD ceremonies
  for documentation, configuration, generated output, or mechanical edits.
- Validate the container and CI contract through the repository's real Make-backed checks.
  Add tests for otherwise unprotected high-risk invariants, not package versions, source text,
  exact shell commands, or other implementation trivia.
- Preserve stable, accessible user flows: check relevant loading/error feedback, theme continuity,
  layout stability, action hierarchy, and unsaved context when changing UI behavior.
- When adding new functionality that implies access restrictions, ask which user roles should have
  access unless the role policy is already specified. Do not ask this for public/unrestricted
  functionality or when existing instructions already define the role access.
- Every new HTTP handler must be explicitly classified as public, admin, or internal before
  implementation. Public API stays under `/api/*`, admin-panel API stays under `/api/admin/*`, and
  authentication and account management remain outside this service's HTTP surface.
  Admin UI flows must not reuse public routes when they need privileged data, privileged controls,
  or behavior that may diverge later; duplicate the transport handler instead and keep shared
  schemas/use cases below the HTTP boundary.
- Keep the admin dashboard as a standalone cross-domain, role-specific composition page; dashboard
  widgets and business logic remain owned by their source domains.
- Privileged behavior must be enforced by backend guards and use cases. Cover each protected path
  with an API or use-case test.
- Keep business authorization expressed through the neutral `core.identity` contracts. Do not add
  service-local login, refresh, logout, password hashing, user/session persistence, or token-key
  handling; authentication adapters belong at the external identity integration boundary.
- Do not add default values in real production code. API parameters, schemas, dataclasses, settings, helpers, services, and infrastructure-facing code should require callers or environment configuration to pass values explicitly. Filter dataclasses may define defaults for omitted filters, pagination, relationship-loading switches, and list-mode switches when the default means "do not apply this filter" or preserves the normal list behavior; tests, test helpers, and factories may keep defaults when they make test setup clearer.
- Avoid `None`/`null` in production schemas, DTOs, and persisted structured content when a truthful
  non-null representation exists. Prefer empty strings for intentionally blank text, empty
  collections for blank lists, and explicit enum values such as `notSet` for unset finite states.
  Keep `None`/`null` only where absence is semantically necessary or no valid non-null
  representation exists, such as unknown dates, optional filters, external contract fields that are
  explicitly nullable, or framework/browser APIs that naturally return null.
- Fix warnings introduced by the change or blocking its verification. Report relevant pre-existing
  warnings separately; do not expand the task into unrelated dependency upgrades or cleanup.
- Run the relevant existing Make checks and review the resulting diff before completion. Broaden
  checks for cross-cutting changes or unresolved risk, not merely to repeat passing verification.
  Report actual results and any relevant checks that could not run.
- Read and update documentation, infrastructure, and CI only where the changed contract requires
  it. Propose AGENTS.md changes only for durable, non-duplicate improvements; omit empty reports.
  Keep AGENTS.md content in English.
- Update the public "How this site is built" page when the change materially affects its technical
  story. Keep it conceptual: omit routine implementation details and mutable operational values.
  For substantial user-visible, architectural, security, operations, or delivery milestones, ask
  whether to include a public updates entry; group related work and skip routine maintenance.
- Use existing Make targets for installation, checks, tests, migrations, and local runs. Do not
  bypass them with lower-level validation tools without explicit authorization for the task; report
  a blocked target rather than silently substituting a different check environment.
- The following Make commands are trusted for agent use and may be approved as recurring command
  prefixes when the local Codex permission flow asks for them:
  `make test-backend-unit`, `make test-backend`, `make test-backend-integration`,
  `make tests`, `make tests-fast`, `make tests-coverage`, `make test-unit`, `make test`,
  `make test-integration`, `make tests-coverage`,
  `make types`, `make format-check`, `make ruff-lint-check`,
  `make lint-check`, `make bandit`, `make security-bandit`,
  `make security-pip-audit`, `make vulture`, `make security`,
  `make query-plans-realistic`, and `make query-plans-stress`.
- Before adding any new Make command to the trusted-for-agents list, inspect the target and the
  scripts it delegates to for agent-safety risks, including repository writes, destructive file or
  Docker operations, database migrations or downgrades, dependency installation, network access,
  secret exposure, long-running services, and other broad side effects.
- Check, test, coverage, quality, query-plan, and performance Make targets must be self-contained:
  they should conditionally prepare dependencies, load the required test environment, start required
  test services or local backend processes, prepare deterministic data where applicable, and clean
  up only resources they started themselves.
- Keep Makefiles as thin wrappers only: Make recipes may call Bash scripts under the relevant
  `scripts/` directory or delegate to nested Makefiles with `$(MAKE) -C ...`, while command logic,
  env loading, shell branching, Docker orchestration, cleanup, and tool invocations belong in
  dedicated scripts such as `scripts/`.
- Do not change `uv.lock` unless dependencies intentionally changed.
- When changing any library, dependency, runtime, or tool version, update the matching badges in `.github/badges/` in the same change.
- Do not commit real or production secrets, tokens, private keys, or environment values.
  Configuration must flow through environment-backed settings. Deterministic non-secret test
  credentials may be committed only in dedicated test fixtures or test environment files and must
  never be usable outside tests.
- UI localisation is backend-bundle driven: user-facing interface strings come from the backend
  i18n catalog, while database/content localisation is selected explicitly through the owning API.
  Read-facing core entities and read models should expose language-neutral projected fields such as
  `title`, `name`, and `content`, populated with the already selected localization instead of
  carrying parallel `*_ru` / `*_en` fields. Write and persistence contracts may keep explicit
  translation fields when both languages are required. Do not add arbitrary language strings,
  implicit fallbacks, or generic translation tables without an explicit design change.
- User-authored Markdown or HTML must render only through the centralized sanitized renderer. Do
  not bind raw authored content to `[innerHTML]`, use `bypassSecurityTrustHtml`, or add a new
  Markdown renderer without XSS regression tests for `<script>`, event-handler attributes, and
  unsafe URL schemes.
- Keep agent access as a separate private machine contour. Production transport is only the
  Litestar REST API at `https://agent.<APP_DOMAIN>:18083/internal/agent/v1`, bound to
  `VPN_BIND_ADDRESS` and authenticated by nginx with distinct client certificates. MCP exists only
  as a local stdio bridge. Preserve distinct machine identities, explicit scopes, the closed
  allowlisted REST/tool surface, server-forced Draft behavior, privacy-safe audit, and the isolated
  trusted nginx-to-backend network contour. Never weaken availability with a public/plaintext
  listener, bearer fallback, shared certificate, human-identity reuse, generic CRUD/HTTP/SQL/shell
  access, publishing, deletion, structure mutation, or server-side URL fetching. Detailed backend
  rules belong in `AGENTS.md` and `docs/agent-access.md`.
- More specific instructions live in nested `AGENTS.md` files under `src/core/`, `src/infra/postgresql/`, and `tests/`.


---

# Backend Instructions

These rules apply to all backend-owned code, configuration, tooling, documentation, and supporting
files at the project root. Shared runtime and deployment infrastructure belongs to the sibling
`infra` repository.

## Code Style

- Use `pyproject.toml` as the source for formatting, lint, and typing configuration.
- No docstrings unless interface is non-obvious from types
- Comments: only for non-obvious WHY, never WHAT
- No Python class name may start with a leading underscore anywhere in the project, including
  production code, tests, migrations, scripts, and performance tooling; there are no exceptions.
  Give every class a clear public name and control module exports through import/export boundaries
  rather than private class naming.
- Keep environment/configuration values, shared operational limits, and configurable policy values
  in `src/infra/config/constants.py`. Domain invariants, parser-specific rules, adapter-local
  mappings, and other implementation constants belong with the domain, parser, or adapter that owns
  them. Core code must receive infrastructure-owned configuration through schemas, constructor
  parameters, or IOC wiring, while infra and entrypoint code may import `constants` directly when
  that layer owns the wiring.

## Layers

| Layer | Path | Responsibility |
|---|---|---|
| Domain | `src/core/` | Business logic. Pure Python only. |
| Persistence | `src/infra/postgresql/` | SQLAlchemy models + concrete storage implementations |
| Interface | `src/entrypoints/litestar/` | HTTP handlers, API endpoints, auth middleware |
| DI | `src/infra/ioc/` | Dishka providers. Wiring only, no logic |
| Config | `src/infra/config/` | Pydantic settings, logging setup |
| File storage | `src/infra/s3/` | S3-compatible files adapter for MinIO |

## Tooling Boundaries

- Performance and test tooling may import reusable application contracts from `src`, such
  as enums, schemas, factories, and public helpers, but tooling-specific infrastructure must live
  with that tooling. Do not create performance-only or test-only support modules under
  `src`; keep performance support under `performance/` and test support under
  `tests/`.

## Operation Boundaries

- Do not model entity mutation methods as `upsert` when the behavior can create, update,
  delete, or otherwise mutate different state. Use explicit operation-specific names and methods
  such as `create_*`, `update_*`, `delete_*`, `publish_*`, or `set_*` so callers cannot
  accidentally trigger broader behavior than intended.

## Business Logic Boundaries

- Business-operation orchestration and flows that coordinate multiple storages belong in domain use
  cases under `src/core/**/use_cases.py`. Invariants and behavior owned by one entity or
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
  `src/entrypoints/litestar/**` module owned by the HTTP entrypoint layer, not in `core`.
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
  `src/entrypoints/litestar/response_cache.py`. Use a `ResponseCacheDomain`
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
- Response-cache warmers live under `src/entrypoints/taskiq/cache_warm/` and must write
  Litestar-compatible msgpack-encoded ASGI response messages through `ResponseCacheDomainStore`.
  Do not write raw JSON response-cache payloads.

## Background Tasks

- TaskIQ entrypoints live under `src/entrypoints/taskiq/`.
- Keep `src/entrypoints/taskiq/broker.py` as the shared broker and
  `src/entrypoints/taskiq/worker.py` as the worker/scheduler registry entrypoint.
- Put domain task wrappers in domain packages such as
  `src/entrypoints/taskiq/cache_warm/tasks.py`; do not collect unrelated tasks in a
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
  `src/entrypoints/litestar/api/agent_access/` layout, with authentication/audit middleware
  and composition helpers in the common Litestar packages. Keep Agent authentication, exception
  mapping, request limits, transaction rollback, and audit behavior scoped to that router/path, and
  exclude it from human authentication and OpenAPI. nginx may forward only five business
  operations plus two certificate-rotation operations through the exact mTLS allowlist. The public
  listener must return `404` for the internal path and strip caller-supplied certificate headers.
  Do not add a separate Agent process/socket, remote MCP endpoint, human authentication,
  generic HTTP proxying/CRUD, SQL, shell, publishing, deletion, structure mutation, or server-side
  URL fetch.
- The local stdio MCP bridge under `src/entrypoints/agent_bridge/` exposes only
  `claim_next_matrix_question`, `get_matrix_authoring_context`, `search_matrix_resources`,
  `save_matrix_question_draft`, and `release_matrix_question_claim`. Keep only MCP schemas, tool
  registration/mapping, and the sanitized exception boundary there; `src/agent_bridge.py`
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

- SQLAlchemy models and database storages live only under `src/infra/postgresql/`.
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
