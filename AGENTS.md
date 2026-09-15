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
- Auth: PASETO (pyseto) + Argon2 password hashing
- Logging: structlog + ECS logging + Sentry SDK
- Frontend: Angular 22 hybrid SSR/CSR + Bootstrap 5, served by a frontend-owned Node.js SSR image
- Edge: nginx reverse proxy for TLS, `/api/*`, exact `/sitemap.xml` and `/robots.txt`, frontend, the public MinIO object endpoint, and VPN-only internal web panel routing

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
- Validate infrastructure through its real Make-backed build, configuration, or runtime checks.
  Add tests for otherwise unprotected high-risk invariants, not package versions, source text,
  exact shell commands, or other implementation trivia.
- Preserve stable, accessible user flows: check relevant loading/error feedback, theme continuity,
  layout stability, action hierarchy, and unsaved context when changing UI behavior.
- When adding new functionality that implies access restrictions, ask which user roles should have
  access unless the role policy is already specified. Do not ask this for public/unrestricted
  functionality or when existing instructions already define the role access.
- Every new HTTP handler must be explicitly classified as public, admin, or internal before
  implementation. Public API stays under `/api/*`, admin-panel API stays under `/api/admin/*`, and
  auth/account remain separate cross-cutting contours under `/api/auth/*` and `/api/account/*`.
  Admin UI flows must not reuse public routes when they need privileged data, privileged controls,
  or behavior that may diverge later; duplicate the transport handler instead and keep shared
  schemas/use cases below the HTTP boundary.
- Keep the admin dashboard as a standalone cross-domain, role-specific composition page; dashboard
  widgets and business logic remain owned by their source domains.
- Privileged behavior must be enforced by backend guards and/or use cases, not only by hiding or
  disabling frontend controls. When a UI hides actions based on role or auth state, keep a matching
  backend authorization check and cover the protected path with an API/use-case test.
- Authentication uses explicit `Authorization` bearer access tokens plus a Secure, HttpOnly,
  SameSite session cookie scoped to refresh/logout under `/api/auth/*`. Preserve the required CSRF
  guard header, Fetch Metadata checks, cookie policy, and server-side verification tests. Before
  expanding browser-sent credentials to any additional state-changing handler, design and test the
  matching CSRF boundary in the same backend/frontend change.
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
  `make test-frontend`, `make tests`, `make tests-fast`, `make tests-coverage`,
  `make tests-coverage-frontend`, `make -C backend test-unit`, `make -C backend test`,
  `make -C backend test-integration`, `make -C backend tests-coverage`,
  `make -C backend types`, `make -C backend format-check`, `make -C backend ruff-lint-check`,
  `make -C backend lint-check`, `make -C backend bandit`, `make -C backend security-bandit`,
  `make -C backend security-pip-audit`, `make -C backend vulture`, `make -C backend security`,
  `make performance-lighthouse`, `make query-plans-realistic`,
  `make query-plans-stress`,
  `make -C frontend test`, `make -C frontend test-coverage`,
  `make -C frontend tests-coverage`, `make -C frontend lint`, `make -C frontend security`,
  `make -C frontend typecheck`, `make -C frontend format-check`, `make -C frontend ssr-smoke`,
  and `make -C frontend build`.
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
  dedicated scripts such as `backend/scripts/`, `frontend/scripts/`, and `infra/scripts/`.
- Do not change lock files (`backend/uv.lock`, `frontend/package-lock.json`) unless dependencies intentionally changed.
- When changing any library, dependency, runtime, or tool version, update the matching badges in `.github/badges/` in the same change.
- Frontend npm installs must enforce peer dependency contracts. Resolve Angular, TypeScript, and tooling peer dependency conflicts in `frontend/package.json` and `frontend/package-lock.json` instead of using `--legacy-peer-deps` or `--force`, except for an explicitly documented temporary workaround with a TODO and removal plan.
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
- Root Docker Compose and `infra/**` changes must preserve the current private-network and public
  exposure baseline. Do not add public service ports, host networking, privileged containers,
  Docker socket mounts, broad capabilities, or root runtime users unless explicitly required and
  accompanied by a documented security tradeoff. Detailed nginx, CSP, VPN, and edge-routing rules
  belong in `infra/AGENTS.md`.
- Keep agent access as a separate private machine contour. Production transport is only the
  Litestar REST API at `https://agent.<APP_DOMAIN>:18083/internal/agent/v1`, bound to
  `VPN_BIND_ADDRESS` and authenticated by nginx with distinct client certificates. MCP exists only
  as a local stdio bridge. Preserve distinct machine identities, explicit scopes, the closed
  allowlisted REST/tool surface, server-forced Draft behavior, privacy-safe audit, and the isolated
  trusted nginx-to-backend network contour. Never weaken availability with a public/plaintext
  listener, bearer fallback, shared certificate, human PASETO reuse, generic CRUD/HTTP/SQL/shell
  access, publishing, deletion, structure mutation, or server-side URL fetching. Detailed backend
  and edge rules belong in `backend/AGENTS.md`, `infra/AGENTS.md`, and `docs/agent-access.md`.
- More specific instructions live in nested `AGENTS.md` files under `infra/`, `backend/`,
  `backend/src/core/`, `backend/src/infra/postgresql/`, `backend/tests/`, `frontend/`,
  `frontend/src/app/`, `frontend/src/app/core/editor/`, and
  `frontend/src/app/features/admin-panel/`.
