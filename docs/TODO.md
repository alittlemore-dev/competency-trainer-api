# TODOs

## Development Stages

### Minimum Viable Product (MVP)

- [x] Competency matrix grid/table view
- [x] Public site-build case-study home
- [x] Contact form
- [x] Articles (previous MVP core-only implementation)
- [x] Admin panel via SQLAdmin

- [x] Add Databasus for database backups
- [x] Configure Let's Encrypt
- [x] Remove password_hash from the User domain model
- [x] Remove the mentorship section.
- [x] Fix static files on MinIO and the backup service.
- [x] (SEO) Add a canonical link
- [x] Validate CSS (focus on overriding Bootstrap variables)
- [x] Move Bootstrap (and other files as needed) to the static folder
- [x] Rebuild admin panel on Litestar
  - [x] Remove SQLAdmin
    - [x] Remove admin startup (docker, create_admin + Makefile)
    - [x] Move file upload handling to Litestar admin handlers
    - [x] Move apply_template_callables to Litestar
    - [x] Remove unused Litestar settings (admin, auth)
    - [x] Remove admin usage from code
    - [x] Remove sqladmin dependencies from uv
  - [x] Edit competency matrix directly on the site (partial)
    - [x] (BACK) Published filter for matrix questions (admin only)
    - [x] (FRONT) Toggle for question list view: published only vs all
    - [x] (BACK) Extended detail response for matrix questions (includes question status)
    - [x] (BACK) CRUD for matrix questions (including nested entities) + guard
      - [x] Create
      - [x] Update
    - [x] Delete
    - [x] Publish
    - [x] Unpublish
    - [x] Normalize sheet/section/subsection structure into database tables and use an inline admin picker for question authoring
    - [x] (BACK) Guard admin file upload endpoints
    - [x] (FRONT) Delete button on question detail
    - [x] (FRONT) Publish/Unpublish button (depending on status)
    - [x] Import competency matrix questions into the shared queued-question model
    - [x] Quick-create competency matrix questions into the shared queued-question model
  - [x] Basic auth and edit permissions (PASETO without sessions. Sessions later)
    - [x] (FRONT) Login page with login button on the main page (hidden for now)
    - [x] (BACK) Login logic
    - [x] (FRONT) Logout button on the main page (hidden for now)
    - [x] (BACK) Logout logic (no-op for now)
    - [x] (BACK) Auth guard (only admins can log in for now)
    - [x] (BACK) Anonymous user
- [x] Smoke test
  - [x] Competency matrix search works as before in grid/table view
  - [x] Matrix question modal opens, code blocks render correctly
  - [x] Run docker-compose and verify related services

### MVP Improvements

- [x] (SEO) Add schemaMarkup link
- [x] Check site performance
  - [x] Add Locust smoke/baseline scaffolding and CI report artifacts
  - [x] Validate selected Locust API responses against backend response schemas
  - [x] Add reusable PostgreSQL query-plan harness for real compiled search queries
  - [x] Tune Locust thresholds from real baseline reports
  - [x] Expand Locust scenarios with seeded article/detail/matrix data
  - [x] Add Lighthouse CI with strict quality/performance gates for Angular hybrid SSR/CSR routes
  - [x] Lighthouse audit — fix non-performance errors and enforce strict gates
- [x] Add public "how this site is built" engineering case-study page.
- [x] Add privacy-safe article analytics (public views, engaged views, anonymous reactions).
- [x] Move tests to backend and create a src subfolder for backend
- [x] Deploy to a remote server
  - [x] Choose hosting
  - [x] Wire up missing secrets and vars
  - [x] Run deployment strictly from the GitHub workflow
  - [x] Remove the unpublished-contract compatibility rule from `AGENTS.md`
  - [x] After deployment, log in to internal services over WireGuard and verify auth
    - [x] MinIO Console via `http://<VPN_BIND_ADDRESS>:18081`
    - [x] Databasus via `http://<VPN_BIND_ADDRESS>:18082`
  - [x] Load the real competency matrix content from the current Google Docs source into the database before first deployment.
  - [x] Closed beta test with real users (friends, colleagues). Collect feedback and fix critical bugs.

### Security and Infrastructure

- [x] Dependency scanning (pip-audit, Bandit, Trivy)
- [x] VPN for accessing internal systems
- [x] Add Dependabot to the repository
- [x] Bot protection for the site
  - [x] Basic nginx edge rate limits for login, contact, public articles, and admin search endpoints
- [ ] Pin Docker image tags currently using latest in compose/build workflows.
- [x] Make frontend/matrix localStorage usage SSR-safe where services/components still access it directly.
- [x] Add architecture-boundary checks so core code cannot import infrastructure/framework modules directly.
- [x] Move DB migration out of app_lifespan into a separate task (possible in docker-compose)
- [x] Replace uvicorn with Granian
- [x] OWASP Top 10 compliance check completed; remaining remediation is tracked under Security audit.
- [x] Security audit
  - [x] Find a web application security checklist and go through it.
  - [x] Regular users cannot access internal web panels without VPN.
  - [x] Build a threat model (who is the attacker, what do they want, etc.). Write to docs.
  - [x] HTTP security headers in responses
    - [x] Strict-Transport-Security
    - [x] X-Content-Type-Options: nosniff
    - [x] X-Frame-Options: DENY
    - [x] Referrer-Policy: no-referrer
    - [x] Content-Security-Policy
  - [x] HTTPS and TLS
    - [x] Public HTTP redirects to HTTPS; internal VPN panels may use HTTP over WireGuard.
    - [x] TLS ≥ 1.2
    - [x] Certbot auto-renews
    - [x] No internal services are exposed to the public
  - [x] XSS
    - [x] All user-supplied data is escaped
    - [x] No `| safe` without 100% certainty
    - [x] Cannot save `<script>` to DB and render it. Check DB for such entries.
    - [x] CSP in place
    - [x] Main Angular SSR scripts use nonce-based CSP; Swagger UI docs keep a route-scoped inline/CDN exception.
    - [x] Remove remaining `style-src-attr 'unsafe-inline'` by refactoring Angular style bindings and overlay positioning.
  - [x] Passwords never logged
  - [x] Hashing: unique salt used
  - [x] Every protected handler checks the user (guards where needed)
  - [x] No role-based "hide button" logic without backend enforcement
  - [x] All validation exists on the backend. Frontend can duplicate it, but never be the only layer.
  - [x] Docker and infrastructure
    - [x] App-owned backend, frontend, and nginx runtime services run with `read_only: true`
    - [x] App-owned backend, frontend, and nginx writable paths are limited to `/tmp` and explicitly needed read-only volumes
    - [x] App-owned backend, frontend, and nginx do not write to `/etc`, `/usr`, or `/bin`
    - [x] No bind mounts like: `- ./:/app`
    - [x] App-owned backend, frontend, and nginx images do not run as root
    - [x] All runtime containers have explicit non-root UID/GID
      - [x] Backend, frontend, nginx, PostgreSQL, Valkey, and MinIO have explicit non-root UID/GID
    - [x] Project Dockerfiles do not install or use sudo
    - [x] User-defined networks used
    - [x] Only nginx exposed to the public
    - [x] No hardcoded cross-service public/private IPs outside Docker-required resolver/self-healthchecks
    - [x] Services accessible only by network name
    - [x] No localhost references between services
    - [x] No sensitive data in `docker inspect`
    - [x] Logs aren’t written to files inside containers
    - [x] Log rotation in place
    - [x] All services have health checks
    - [x] Nginx does not forward traffic to an unhealthy backend
    - [x] Adequate restart policy
    - [x] Image versions pinned for locally built backend, frontend, nginx, and MinIO runtime images
    - [x] No `latest` tags for Docker runtime images or image-security workflow builds
    - [x] Minimal packages
    - [x] Nginx not root
    - [x] Nginx has no write access outside `/tmp`
    - [x] No `proxy_pass` to localhost
    - [x] No `network_mode: host`
    - [x] No `privileged: true`
    - [x] No `/var/run/docker.sock` bind mount
    - [x] No `cap_add` unless strictly necessary
    - [x] No `devices:` unless strictly necessary
    - [x] App-owned backend, frontend, and nginx runtime services use `cap_drop: [ALL]`
    - [x] No secrets in images
    - [x] Infrastructure services are not exposed externally
      - [x] PostgreSQL
      - [x] Valkey
    - [x] Postgres, Valkey, MinIO have no `ports`
    - [x] MinIO Console protected by VPN-only access; public MinIO object endpoint remains intentionally public for files.
    - [x] Databasus protected by auth
    - [x] `.env` not in git
    - [x] No secrets in logs
    - [x] All keys are long and random
    - [x] No stacktrace shown to users
    - [x] Firewall enabled on host (ufw/iptables)
    - [x] Only `80/tcp`, `443/tcp`, and the chosen WireGuard UDP port are open publicly.
    - [x] SSH by key only. Password login disabled.
  - [x] Rate limiting and bot protection
    - [x] Rate limit on login, registration, and password reset (registration/password reset are not implemented)
    - [x] IP / fingerprint-based limiting (IP-based at nginx edge)
    - [x] No unlimited requests to heavy endpoints
  - [x] Backup & recovery
    - [x] Backups encrypted
    - [x] Backups are not publicly accessible
    - [x] Restore tested
    - [x] No access to back up a panel without auth
  - [x] Supply chain
    - [x] Dependency versions pinned, including required local runtime image tags
    - [x] Dependencies updated regularly
    - [x] No pip install from untrusted sources

### Tracing and Monitoring

- [x] Add optional app-side slow SQL query timing logs without raw parameter values
- [ ] Enable slow SQL query timing logs in staging/production with explicit thresholds
- [ ] Error alerts to Telegram bot
- [ ] Wire frontend GlobalErrorHandler to Sentry in production.
- [ ] Add Web Vitals collection/reporting for public SSR routes after deployment.
- [ ] Add maintainer status dashboard for uptime, backups, restore tests, service health, and production errors.
- [ ] Set up Grafana + Prometheus + Loki
- [ ] Set up PostgreSQL performance visibility
  - [ ] Enable `pg_stat_statements` for aggregate query timing, calls, rows, and cache-hit signals
  - [ ] Enable safe `auto_explain` logging for slow query plans
  - [ ] Alert on long-running queries, lock waits, deadlocks, and connection pool saturation
  - [ ] Add dashboard panels for top queries by total time, mean time, p95-ish latency, and calls
- [ ] Detect likely N+1 and query explosions
  - [ ] Count SQL statements per HTTP request
  - [ ] Warn when one request exceeds the query-count threshold
  - [ ] Add tests for query-count budgets on expensive API endpoints
- [ ] Add Prometheus exporters
  - [ ] PostgreSQL exporter
  - [ ] nginx exporter
  - [ ] node/container exporter
  - [ ] Valkey-compatible Redis exporter
  - [ ] MinIO exporter or built-in metrics scrape
- [ ] Add Grafana dashboards
  - [ ] API latency p50/p95/p99, request rate, and 4xx/5xx rate
  - [ ] DB query latency, locks, connections, and disk usage
  - [ ] nginx upstream status and response latency
  - [ ] container CPU/RAM/restarts
  - [ ] backup freshness and restore-test status
- [ ] Add operational alerts
  - [ ] p95 latency regression
  - [ ] 5xx spikes
  - [ ] event loop lag
  - [ ] TLS certificate expiry
  - [ ] backup failure or stale backup
  - [ ] disk pressure
- [ ] Set up a container health monitoring service
  - [ ] Send notifications on a container crash
  - [ ] Send notifications on high resource usage (CPU, RAM)
- [ ] Security audit
  - [ ] Regular users cannot access Grafana without VPN.

### Frontend

- [x] Replace native admin filter selects with accessible custom dropdowns whose open option list
  follows the site's green active-color theme consistently across operating systems.
- [x] Keep background pages fixed while every modal routes backdrop and chrome scrolling to its content.
- [x] Make frontend adaptive and flexible to correctly opening on smartphones and thin screens.
- [x] Optimize page load times (CSS/JS minification, image optimization). Consider CDN for static files.
- [x] Cookie consent
- [x] Fix question search on the frontend: empty sections should also be removed
- [x] Make text selection colour match the site theme
- [x] Add more feedback during API requests (notifications, errors, etc.)
- [x] Improve the custom date picker with in-calendar month and year selection.
  - [x] Make the current month and year in the calendar header clickable.
  - [x] Open month/year selection in the same calendar popover.
  - [x] Use a predefined localized month list for month selection.
  - [x] Support year selection with an in-calendar stepper.
- [x] Resolve frontend npm peer dependency conflicts and remove `--legacy-peer-deps` from install flows
  - [x] Align TypeScript with Angular CLI/build tooling peer dependency ranges so `npm ls typescript` exits cleanly
  - [x] Remove `--legacy-peer-deps` from frontend dependency installation scripts and Docker build
- [x] Migrate to the Angular
  - [x] Target architecture
    - [x] Use Angular as a hybrid SSR/CSR frontend served by a frontend-owned Node.js runtime
    - [x] Keep Litestar as the backend API only (`/api/*`, `/api/docs`, service endpoints)
    - [x] Configure frontend fallback/hydration for CSR routes
    - [x] Keep legacy Litestar/Jinja/HTMX views only during migration
    - [x] Remove legacy views, templates, HTMX, Hyperscript, and template-only static files after parity
  - [x] API contracts and client integration
    - [x] Align Angular services with public/admin backend endpoints (`/api/competency-matrix/*`, `/api/admin/competency-matrix/*`, `/api/contacts`, `/api/auth`, `/api/account`, `/api/admin/files`, `/api/admin/wiki-links`)
    - [x] Add DTO interfaces matching backend camelCase response aliases
    - [x] Add explicit DTO -> UI model mapping functions in feature `models/`
    - [x] Add frontend service tests for endpoint URLs, query params, and response mapping
    - [x] Add missing backend API endpoints only where data currently exists only in Jinja templates
    - [x] Keep feature services using `ApiClient`; do not inject raw `HttpClient` outside `core/http/`
  - [x] Frontend app shell
    - [x] Route parity: `/how-this-site-is-built`, `/competency-matrix`, `/sitemap`, `/404`
    - [x] Redirect `/` to the localized site-build case study
    - [x] Header with current navigation and active route state
    - [x] Footer with docs, source, sitemap, and social links
    - [x] Global alert/notification area for API success and error feedback
    - [x] Theme service with `data-bs-theme`, localStorage persistence, and initial theme application
    - [x] Grid-only competency matrix view
    - [x] Move shared styles from `src/static/styles.css` to Angular SCSS structure
    - [x] Move public assets from `src/static/` to `frontend/public/`
  - [x] SEO and root files
    - [x] Page title and meta description per route
    - [x] Open Graph and Twitter meta tags for public pages
    - [x] Canonical URL per route
    - [x] favicon and icon variants
    - [x] Backend-generated `robots.txt`
    - [x] Backend-generated `sitemap.xml`
    - [x] sitemap page
    - [x] `/.well-known/appspecific/com.chrome.devtools.json`
  - [x] Competency matrix
    - [x] Sheets loading from `/api/competency-matrix/sheets`
    - [x] Selected sheet persistence in localStorage
    - [x] Question grid/table from `/api/competency-matrix/items`
    - [x] Preserve section -> subsection -> grade grouping
    - [x] Grid/table layout
    - [x] Search that hides empty sections and subsections
    - [x] Public matrix always uses public endpoints; admin `onlyPublished` filters live in the admin matrix workspace
    - [x] Question detail modal/page from public detail endpoints
    - [x] Markdown rendering for answers and resource context
    - [x] Code highlighting for Markdown code blocks
    - [x] External resources list
    - [x] Loading, empty, and error states for every API-backed view
  - [x] Public home
    - [x] Use the site-build case study as the public home
    - [x] Keep direct contact via footer links
  - [x] Auth and account
    - [x] Auth token storage strategy
    - [x] HTTP interceptor that sends `Authorization: Bearer <token>`
    - [x] 401 handling that opens login flow or redirects to login state
    - [x] Login modal
    - [x] Logout button
    - [x] navbar profile info
    - [x] Current user loading from `/api/account/base`
    - [x] Moderator/admin panel access based on account role, with backend guards still enforced
  - [x] Deployment and legacy cleanup
    - [x] Build Angular in CI/CD
    - [x] Build Angular as an independent frontend Docker image
    - [x] Serve Angular hybrid SSR/CSR from a frontend Node.js runtime
    - [x] Proxy `/api/*` and `/api/docs` from nginx to Litestar
    - [x] Smoke test direct route loads (`/how-this-site-is-built`, `/competency-matrix`, `/sitemap`)
    - [x] Smoke test browser refresh on Angular routes
    - [x] Remove `views_router` from Litestar app after Angular parity
    - [x] Remove Jinja templates and HTMX/Hyperscript dependencies after Angular parity
    - [x] Remove backend static vendor files replaced by Angular build assets
- [x] Replace static sitemap page with content-driven localized sitemap links.
- [x] Add and edit competency matrix questions
  - [x] Search through existing external resources
  - [x] Edit mode for a specific question in the admin matrix workspace
  - [x] Button and form for adding a question to a matrix section in the admin matrix workspace
  - [x] ToastUI should work through backend-owned file uploads, display uploaded files, edit content, save content.
- [x] "404" page
- [x] Check for possible convert raw Markdown to HTML on the frontend side only
- [x] Security audit
  - [x] Moderators and admins can edit, add, and delete matrix questions in the admin panel

### Articles

- [x] Content localisation for articles
  - [x] Store article `title_ru`, `title_en`, and `content_ru` / `content_en` as required columns, with article folders normalized into a required localized folder table
  - [x] Store tag `name_ru` and `name_en` as required columns
  - [x] Keep article `slug` and tag `slug` as single stable English identifiers shared across languages
  - [x] Require all RU/EN fields on create and update for both draft and published articles
  - [x] Read article list, detail, tree, tag list, and tag search results in the selected content language
  - [x] Search by `search_vector_ru` or `search_vector_en` depending on requested language
  - [x] Keep `tagSlug` as one language-neutral English filter
  - [x] Add admin-panel content authoring UI controls for editing RU and EN article fields
  - [x] Manage RU/EN article tags on a dedicated admin page and attach existing tags through the article picker
  - [x] Delete article tags permanently with their article associations; do not expose soft deletion or restoration
  - [x] Update the init Alembic migration during pre-deployment development
  - [x] Generate one follow-up autogen migration to verify SQLAlchemy models and migrations are consistent
  - [x] Cover backend and frontend behaviour with focused tests
- [x] Hide/Publish articles
- [x] Show articles sorted by publication date
- [x] Show articles in a side panel with a tree view
- [x] Show public article view counters and anonymous reactions
- [x] Admin article statistics by date range, source category, and reactions
- [x] Filters by tags
- [x] Filters by publish date range
- [x] Search articles by title and content
- [x] Article authoring and public articles release
  - [x] Use articles as the authored content model and keep save/publish independent from SEO warnings
  - [x] Add nullable RU/EN SEO metadata, managed cover file id, computed cover URL, and cover alt fields to article storage/API
  - [x] Require an explicit `metadata` request object while allowing individual metadata fields to be `null`
  - [x] Add article form controls for SEO metadata and cover upload through the backend file flow
  - [x] Expand the live admin SEO panel with metadata, cover, alt, and wiki-link checks
  - [x] Add toggleable article/social preview for the selected language
  - [x] Render typed `[[articles:<slug>]]` / `[[matrix:<slug>]]` links as internal localized links
  - [x] Warn when wiki links point to missing targets available in the admin target registry
- [ ] Extend managed `FileModel` metadata when the next file workflow needs it:
  - [ ] lifecycle status (`uploading`, `ready`, `deleteFailed`, `processingFailed`)
  - [x] original upload integrity metadata (`original_sha256`) for purpose-scoped dedupe
  - [ ] storage integrity metadata such as S3 `etag`
  - [ ] backend identifier (`storage_backend`) for future S3/local/CDN switching
  - [ ] ownership/audit metadata (`uploaded_by_username`)
  - [ ] image metadata (`width_px`, `height_px`) for cover/content image validation
  - [ ] processing metadata (`original_mime_type`, `original_size_bytes`, `processing_status`) for WebP conversion/compression
  - [ ] attachment safety metadata (`scan_status`, `scanned_at`) before broader attachment workflows
  - [ ] separate file variants table instead of adding variant columns to `FileModel`
- [x] Add backend file-content signature checks during upload so duplicate files are not uploaded
  repeatedly; compute a stable signature such as `sha256`, return or link to an existing matching
  managed file when appropriate, and upload a new object only when no reusable file exists.
- [x] SEO Foundation release
  - [x] Add Angular hybrid rendering for public article routes while keeping interactive/admin routes CSR
  - [x] Add `/ru` and `/en` canonical URL prefixes
  - [x] Generate dynamic `sitemap.xml` and `robots.txt`
  - [x] Emit Article JSON-LD/Open Graph metadata from stored article metadata
  - [x] Add HTML smoke tests for public article pages and missing-article `404/noindex`
- [x] Matrix public SEO release
  - [x] Add explicit matrix question slugs
  - [x] Add separate public matrix question pages
  - [x] Preserve modal interaction from the matrix overview
  - [x] Emit FAQPage structured data after public question pages exist
- [x] Add owner/admin/moderator content workspace for articles with admin filters, create modal, edit detail route, a dedicated tag-management page, and publish/delete dropdown actions.
- [ ] Add article editorial queues and richer workspace views.
- [ ] Add content health checks for articles: SEO metadata, cover alt text, stale translations, wiki-link issues, and broken external links.
- [ ] Add article revision history with diff and restore.
- [ ] Add autosave / local draft recovery for article editing.
- [ ] Add protected preview links for unpublished articles.
- [ ] Add scheduled publishing for articles.
- [ ] Add editorial workflow statuses for articles: idea, draft, review, ready, published, archived.
- [ ] Add Obsidian-compatible Markdown import/export for articles.
- [ ] Add privacy-safe AI-assisted authoring for spelling, SEO hints, tags, and RU/EN consistency.
- [ ] TTL (5 min) cache for analytics data
- [x] Security audit
  - [x] Moderators and admins can edit, add, and delete articles in the admin panel
  - [x] Regular users cannot view hidden articles

### Workspace

Workspace is protected owner/admin utilities that live only in the admin panel.

- [x] Operational tools
  - [x] Inspect, clear, and asynchronously warm response-cache domains with observable status.
  - [x] Inspect expired and soon-expiring auth sessions and manually prune expired sessions.
- [x] Team
  - [x] Add owner/admin backend CRUD API under `/api/admin/accounts`.
  - [x] Add team Workspace navigation and routes under `/admin-panel/workspace/team`.
  - [x] Manage owner/admin/moderator usernames, roles, passwords, and active status with owner/admin governance.
  - [x] Enforce a single owner at the database level; reject owner self role/deactivation/delete actions.

### Auth and Users

- [ ] User authentication improvements (possibly via OAuth2)
  - [ ] (FRONT) Register button and form
  - [ ] (BACK) Registration logic
  - [ ] Remove the owner/admin/moderator-only login warning after regular-user authorization/login is implemented
  - [ ] (FRONT) Password recovery button and form (simple confirmation email)
  - [ ] (BACK) Password recovery logic
  - [x] (BACK/FRONT) Add admin session cookie for login/refresh/logout with short-lived access tokens
- [ ] Privacy policy
- [ ] Terms of service
- [x] Personal data processing consent (frontend-only on contact form)
- [ ] Persist personal data processing consent on the backend with timestamp and source when contact requests or user accounts are stored.
- [ ] Add personal-data export/delete request flow.
- [ ] Add retention rules for contact requests, feedback reports, typo reports, subscriptions, and accounts.
- [ ] Password recovery
- [ ] Password confirmation
- [ ] Flashcards from competency matrix (stateful — saved per user)
- [ ] Comments on articles
- [ ] 2FA/MFA for users
- [ ] User profile
  - [ ] Course completion statistics
  - [ ] Edit personal details
  - [ ] Notification settings
  - [ ] Saved flashcard list
  - [ ] Add self-service session management to the user profile: list current account sessions,
        show privacy-safe device labels, and revoke one/all/other sessions outside the admin
        team-member detail flow.
- [ ] Security audit and features
  - [ ] Users cannot interact with other users' profiles. Read-only.
  - [x] No admin access tokens in localStorage
  - [x] Admin auth refresh based on an HttpOnly, Secure, SameSite=Lax session cookie
  - [x] Session invalidation on logout, password change, deactivation, and account deletion
  - [x] Expired sessions are rejected
  - [ ] Add identity-aware brute-force defenses: per-account/username failed-login counters,
        temporary soft lockout or backoff after repeated failures, and generic blocked-login
        responses that do not expose account existence.
  - [ ] Add a durable auth audit trail for login, refresh, logout, session revocation, step-up
        re-auth, role/password/account changes, suspicious events, and blocked attempts without
        storing raw passwords, tokens, raw user agents, or raw IP addresses.
  - [x] Add an absolute session lifetime cap on top of the sliding idle lifetime so refresh cannot
        extend a session beyond its original maximum age.
  - [ ] Add PASETO key rotation with an active signing key, accepted verification keyring, `kid`
        metadata, and an overlap period for tokens signed by retiring keys.
  - [ ] Add step-up re-auth for sensitive actions such as own password changes, account deletion,
        and team/role/password management.
  - [x] Add explicit device/session management: list sessions, revoke one, revoke all or others,
        privacy-safe user-agent display, current-session marker, and last-used timestamp.
  - [ ] Session rotation / refresh-token-family reuse detection for broader user accounts
  - [x] Expired sessions are physically pruned by a scheduled cleanup task

### Flashcards

Flashcards should be implemented strictly after auth implementation for common users.

- [ ] Create flashcards from competency matrix (stateless — no persistence, restart = new set)
- [ ] Create custom flashcards
- [ ] Export user flashcards to .apkg format

### Competency Matrix Improvements

- [x] Content localisation for competency matrix
  - [x] Use stable `sheetKey` values as language-neutral sheet identifiers
  - [x] Localise sheets, sections, subsections, questions, answers, expected answers, resource names, and resource context
- [x] Move sheet, section, subsection to separated tables
- [x] Priority for matrix sheets, sections, and subsections with drag-and-drop admin ordering
- [x] Add a queue list for questions I want to add to the matrix
- [x] Ability to suggest a question for the competency matrix
- [x] Add moderation inbox for suggested matrix questions.
- [x] Add ToastUI Markdown editing to competency matrix answer and expected-answer fields in the shared matrix question form.
- [x] Add RU/EN/RU+EN display modes to the shared matrix question form for localized question, answer, and expected-answer fields.
- [x] Add a provider-agnostic RU-to-EN translation workspace to the shared matrix question form.
  - [x] Add a dedicated translation view with read-only RU source content and editable EN content shown side by side on wide screens and stacked in matching pairs on narrow screens.
  - [x] Pair question, answer, interview expected answer, resource name, and resource context fields so the source and translation stay visually connected.
  - [x] Add per-field "copy RU source" actions with explicit success, unavailable, and failure feedback.
  - [x] Add "copy all RU content for translation" using a structured package that includes stable field and resource identifiers.
  - [x] Preserve Markdown, fenced and inline code, URLs, and typed wiki links in translation packages.
  - [x] Add structured EN package paste/import with validation and a field-by-field preview before applying changes to the form.
  - [x] Show EN translation completeness independently from ordinary non-empty-field validation.
  - [x] Warn when normalized RU and EN content is identical, including the queue-created question text that initially populates both languages.
  - [x] Allow intentionally language-neutral or identical content to be explicitly reviewed so it does not remain a permanent warning.
  - [x] Provide a direct action from translation mode to the EN public preview without changing the current UI language.
- [x] Add a sticky shared matrix question form action footer that supports custom submit labels/actions without queue-specific branching.
- [x] Add a compact shared matrix question form readiness panel for required publication fields.
  - [x] Distinguish fields required to save a draft, blockers that prevent publication, and advisory content-health warnings.
  - [x] Group live readiness results by structure and metadata, RU content, EN content, and attached resources.
  - [x] Show compact per-group and overall progress without hiding the exact missing or suspicious fields.
  - [x] Make each readiness item reveal the required RU/EN display mode, scroll to the related control, and move focus to it.
  - [x] Keep frontend readiness results aligned with backend publication guards and cover both boundaries with behavioral tests.
  - [x] Reuse the same readiness vocabulary in the form, workspace rows, filters, and publication feedback.
- [x] Add an in-form public preview for competency matrix question Markdown and attached resources before saving/publishing.
- [ ] Add a fullscreen single-question queue processing modal that keeps the shared matrix question form wide and shows queue progress/navigation.
  - [ ] Show the current position and remaining available count within the active filtered queue.
  - [ ] Add explicit previous and next navigation without mutating skipped queue entries.
  - [ ] Preserve active queue filters and FIFO context while processing, creating, rejecting, or temporarily leaving for the detail editor.
  - [ ] Skip claimed questions safely and explain when no further available question matches the active filters.
  - [ ] Keep the action footer and readiness summary reachable on desktop, narrow screens, and short viewports.
  - [ ] Move focus into the modal on open, restore it on close, and keep Escape and focus behavior predictable when unsaved changes exist.
- [x] Add queue-only "create and next", "create and edit", "reject and next", and "skip" actions around the shared matrix question form.
- [ ] Add queue-only keyboard shortcuts for fast queued question processing.
  - [ ] Add shortcuts for create and next, create and edit, reject and next, skip, previous, and next.
  - [ ] Do not trigger queue shortcuts while focus is inside inputs, textareas, selects, Markdown editors, dialogs, or other editable controls.
  - [ ] Disable shortcuts while requests or confirmation dialogs are pending and prevent duplicate submissions.
  - [ ] Show a discoverable shortcut reference in the fullscreen processing UI.
- [ ] Persist queue-only last-used structure, grade, and interview frequency defaults for faster repeated question creation.
  - [ ] Apply stored defaults only when the queued question does not already provide the corresponding value.
  - [ ] Scope defaults to the authenticated content manager and keep storage access SSR-safe.
  - [ ] Ignore or clear stale structure identifiers that no longer exist.
  - [ ] Let the user reset persisted queue defaults from the processing UI.
- [ ] Show duplicate/similar-question hints when processing a queued competency matrix question.
  - [ ] Detect normalized exact matches separately from fuzzy similar-question matches.
  - [ ] Search across both RU and EN question text and show structure, grade, status, and similarity context.
  - [ ] Link hints to the existing admin detail page without losing the queued-question draft or queue position.
  - [ ] Keep hints advisory and allow the manager to continue when the similarity is intentional.
- [ ] Add search, filters, and sorting to the competency matrix question queue.
  - [x] Search visible queue question and source metadata case-insensitively.
  - [x] Filter by sheet, grade, and claim availability with explicit unset choices.
  - [x] Persist normalized queue filter state in the URL.
  - [ ] Add sorting while preserving FIFO as the default, including created time, sheet, grade, and claim availability options.
- [ ] Add the ability to split one queued competency matrix question into multiple queued questions.
- [x] Add import preview/confirmation for competency matrix question queue imports with duplicate/validation warnings.
- [ ] Ability to report a typo in the competency matrix
- [ ] Add moderation inbox for report a typo in the matrix questions.
- [x] Add owner/admin/moderator content workspace for matrix questions with richer filters, public preview, edit detail route, and dropdown actions.
- [ ] Add fast matrix question workspace navigation and safe batch actions.
  - [ ] Add previous and next question navigation on the detail page within the current filtered and sorted workspace selection.
  - [ ] Preserve the complete workspace query state and return position when navigating through detail pages.
  - [ ] Make workspace summary cards apply and visibly describe the corresponding draft, missing, dangerous-published, or ready-published filter preset.
  - [ ] Add multi-row selection that remains understandable across pagination and filter changes.
  - [ ] Add batch unpublish, grade change, and interview-frequency change actions with confirmation and per-item results.
  - [ ] Allow batch publication only for ready questions, leave blocked questions unchanged, and report their blockers individually.
  - [ ] Enforce every batch mutation through the same backend authorization and publication rules as single-item actions.
- [ ] Add local autosave and draft recovery for competency matrix question authoring.
  - [ ] Debounce local snapshots of question fields, localized Markdown, structure selection, and attached-resource drafts without saving filter or preview-only UI state.
  - [ ] Scope snapshots by authenticated account and question ID or queued-question ID so drafts cannot cross users or authoring contexts.
  - [ ] Show snapshot time and explicit restore or discard actions when a recoverable draft is found.
  - [ ] Warn when the server version changed after the local snapshot and preview the conflict before restoration.
  - [ ] Clear recovered data after a successful save or explicit discard and expire abandoned snapshots after a documented retention period.
  - [ ] Fail safely with visible non-blocking feedback when browser storage is unavailable or full.
- [ ] Harden existing matrix question management workflows with behavioral regression coverage and manual UX QA.
  - [ ] Cover workspace filter URL -> detail -> back and previous/next navigation without losing context.
  - [ ] Cover queue -> draft creation -> RU-to-EN translation -> EN preview -> publication across focused frontend and backend tests.
  - [ ] Cover unsaved-change, autosave recovery, request failure, retry, and duplicate-submission paths.
  - [ ] Verify keyboard and focus behavior for create, edit, queue, confirmation, preview, and recovery flows.
  - [ ] Manually verify the complete management flow through the existing local stack on desktop, narrow mobile, and short viewport layouts.
- [ ] Add content health checks for matrix questions: stale translations, wiki-link issues, resource issues, and broken external links.
  - [ ] Detect EN content that became stale after its RU source changed and show which localized fields require review.
  - [ ] Include identical RU/EN warnings and explicit intentionally-identical review state in health results.
  - [ ] Detect missing, malformed, or unpublished typed wiki-link targets in both languages.
  - [ ] Detect missing resource translations, attachment contexts, duplicate URLs, and resources no longer referenced by any question.
  - [ ] Check external links asynchronously with SSRF-safe URL policy, bounded timeouts, retries, and cached results.
  - [ ] Add workspace health filters and actionable links that open the affected question and focus the relevant field.
  - [ ] Keep health analysis advisory for drafts and make any publication-blocking subset explicit and backend-enforced.
- [ ] Add self-assessment / interview mode with expected-answer reveal.
- [ ] Track weak matrix topics for later study recommendations.
- [ ] Add matrix question revision history with diff and restore.
  - [ ] Record actor, timestamp, operation, publication state, structure, localized content, and attached-resource changes for each saved revision.
  - [ ] Render field-level and Markdown-aware diffs separately for RU and EN content.
  - [ ] Show resource attachment, context, metadata, and structure changes alongside text changes.
  - [ ] Restore a historical version by creating a new auditable revision instead of destructively rewinding history.
  - [ ] Keep revision reads and restores owner/admin/moderator protected and cover authorization and restore behavior with tests.
- [ ] Add matrix analytics panel for views, engagement, typo reports, and suggestions.
- [ ] Add matrix resource library with deduplication, reuse, tagging, and link checks.
  - [ ] Detect exact and probable duplicate resource URLs before creating a shared resource.
  - [ ] Search and filter resources by localized name, URL, tag, usage, and link-health state.
  - [ ] Show every question using a resource and the impact before shared resource metadata is changed.
  - [ ] Reuse existing localized resource names while keeping per-question RU/EN attachment contexts editable.
  - [ ] Run link checks asynchronously with SSRF protections and expose last-check time and actionable failure state.
  - [ ] Support safe merge of duplicate resources while preserving all question attachments and localized contexts.

### Competency roadmaps

- [ ] Add public direction roadmaps such as Python Backend, Frontend, etc.
- [ ] Dynamic roadmap rendering
- [ ] Links to matrix questions
- [ ] Links to articles
- [ ] Links to resources
- [ ] Links to courses
- [ ] Links to another roadmap (step, after which you may go to the next roadmap)

### Courses

- [ ] Link courses to competency matrix
- [ ] Browse available courses
- [ ] Create a course material step (can include video, text, images, files, tests)
- [ ] Playground for course tests (leetcode- or codewars-like checks)
- [ ] Create courses consisting of material steps
- [ ] Security audit
  - [ ] User cannot edit another user's course progress

### Editor platform

The shared editor is currently Markdown-first. Treat it as a reusable editor platform so future
modes, such as programming-course assignment workspaces, can reuse only the relevant foundation
instead of inheriting every Markdown-specific feature.

Graph views, plugin APIs, and plugin-system support are explicitly out of scope for this roadmap.

- [ ] Complete the custom Obsidian-like Markdown editor roadmap.
  - [x] Add the first stage: modular CodeMirror 6, source/preview tabs, the complete initial
    physical-key command map, smart lists and fences, search, ordered multi-image insertion, and
    centralized sanitized preview ([CodeMirror reference](https://codemirror.net/docs/ref/)).
  - [x] Preserve article tags and typed article/matrix wiki links across the shared-editor
    migration.
  - [x] Highlight supported fenced-code languages consistently in source mode and sanitized
    preview.
  - [x] Add an accessible fullscreen mode with a conventional expand/collapse icon, Escape exit,
    focus and scroll restoration, page-scroll locking, responsive behavior, and no loss of
    selection or unsaved content.
  - [ ] Add a backend-synced editor profile for every authenticated content editor.
    - [ ] Make hotkeys fully configurable with command search, multiple bindings, conflict
      detection, and reset per command, section, or the whole profile.
    - [ ] Add appearance settings for font family, font size, line height, readable width,
      wrapping, line numbers, tab width, editor height, theme, and syntax palette.
    - [ ] Add behavior settings for the default tab, spellcheck, auto-pairs, smart lists and
      fences, Tab behavior, and image insertion.
  - [ ] Add an accessible Markdown command palette with fuzzy search, current shortcuts,
    recent/pinned commands, and a touch/mobile entry point
    ([Obsidian hotkeys](https://obsidian.md/help/hotkeys),
    [command palette](https://obsidian.md/help/plugins/command-palette)).
  - [ ] Add typed wiki-link autocomplete for articles and matrix questions, target preview, and
    missing/unpublished target warnings.
    - [x] Autocomplete typed article and matrix targets and show each target's localized title and
      publication status in the completion list.
    - [ ] Add shared inline missing/unpublished target diagnostics and a content preview without
      making an unavailable target registry look like an empty registry.
  - [ ] Add selection-aware typed wiki-link insertion and deep heading targets
    ([Obsidian internal links](https://obsidian.md/help/links)).
    - [ ] Turn selected text into the custom label when the author types `[[` and then chooses an
      article or matrix target.
    - [ ] Autocomplete headings in the current document and in a selected target, persist stable
      localized fragments, and warn when a referenced heading no longer exists.
  - [ ] Safely refactor typed wiki links when an article or matrix slug changes.
    - [ ] Show the affected localized documents and reference count before confirming a slug
      change.
    - [ ] Rewrite authorized references transactionally while preserving labels, publication
      rules, revision history, and an auditable failure result for every reference not changed.
  - [ ] Add a Markdown outline, heading navigation, and folding for heading, list, and code
    sections.
  - [ ] Add advanced table editing, callouts, footnotes, templates/snippets, math, and diagrams
    only together with centralized renderer support and XSS regression tests
    ([Obsidian Markdown syntax](https://obsidian.md/help/syntax)).
    - [x] Complete the advanced source-preserving table-editing portion through the dedicated
      interactive Markdown table work below.
    - [ ] Add renderer-backed callouts with commands for inserting, wrapping, changing type, and
      creating accessible nested or collapsible callouts.
    - [ ] Add renderer-backed block and inline footnotes with source navigation between each
      reference and definition.
    - [ ] Add reusable templates/snippets with preview, explicit insertion position, and
      placeholder navigation without introducing a second content model.
    - [ ] Add math and diagrams through the centralized sanitized renderer with explicit resource
      limits and safe failure states for malformed or expensive input.
  - [ ] Add the complete Markdown attachment workflow: progress, cancel, retry, required alt text,
    existing-file reuse, and orphan cleanup
    ([Obsidian attachments](https://obsidian.md/help/attachments)).
    - [x] Support ordered image insertion from the picker, paste, and drop flows with a visible
      uploading state plus retry and dismiss actions after failure.
    - [ ] Add per-file progress, in-flight cancellation, required alt-text authoring, existing-file
      selection, and deterministic cleanup of uploads abandoned before a successful save.
  - [ ] Extend Markdown attachments to safe media embeds and author-controlled image presentation
    ([Obsidian embeds](https://obsidian.md/help/embeds)).
    - [ ] Insert and preview supported PDF, audio, and video attachments without exposing private
      object URLs or bypassing consumer-specific upload restrictions.
    - [ ] Let authors set accessible image alt text, caption, and bounded display dimensions while
      keeping the stored Markdown portable and the public layout responsive.
  - [ ] Add RU/EN spelling and grammar assistance, word/character/read-time statistics, and
    localized content diagnostics.
    - [x] Enable native browser spelling with the active RU/EN content language on the shared
      editor surface.
    - [ ] Add grammar assistance, shared word/character/read-time statistics, and localized
      diagnostics with clear source ranges and advisory-only failure behavior.
  - [ ] Add editor profile import/export and settings synchronization between devices.
  - [ ] Add a true source-preserving Live Preview mode that hides inactive Markdown syntax and
    reveals the exact delimiters around the active cursor or selection
    ([Obsidian editing modes](https://obsidian.md/help/edit-and-read)).
    - [ ] Render headings, emphasis, links, lists, tasks, callouts, code, media, and other supported
      syntax inline without replacing the canonical Markdown document.
    - [ ] Preserve selection, history, IME, clipboard, screen-reader output, scroll position, wiki
      link completion, and interactive-table invariants while syntax appears or disappears.
  - [ ] Convert pasted rich HTML into sanitized portable Markdown while retaining an explicit
    plain-text paste path ([Obsidian editor settings](https://obsidian.md/help/settings)).
    - [ ] Preserve supported headings, paragraphs, emphasis, lists, links, tables, quotes, and code
      while dropping scripts, event handlers, unsafe URL schemes, unsupported styles, and hidden
      content.
    - [ ] Keep image paste routed through the existing ordered upload workflow and make every
      conversion result one undoable CodeMirror transaction.
  - [ ] Make task-list checkboxes interactive in Editor and author preview modes.
    - [ ] Toggle the exact canonical `[ ]` or `[x]` marker through an undoable transaction without
      disturbing selection, scroll, nested-list structure, or surrounding Markdown.
    - [ ] Support pointer and keyboard activation with an accessible state while keeping public
      reading views non-mutating.
  - [ ] Add Obsidian-style `==highlight==` and author-only `%%comment%%` syntax through the shared
    parser, commands, presentation, and sanitized renderer
    ([Obsidian formatting syntax](https://obsidian.md/help/syntax)).
    - [ ] Render highlights accessibly and preserve their delimiters in Source and active Live
      Preview editing contexts.
    - [ ] Keep comments visible to authors where appropriate but remove them from public preview,
      rendered pages, excerpts, SEO analysis, search indexing, and public exports.
  - [ ] Add theme-aware indentation guides for nested Markdown lists and other supported indented
    blocks ([Obsidian editor settings](https://obsidian.md/help/settings)).
    - [ ] Keep guides correct across wrapped lines, folding, multi-selection, responsive layouts,
      fullscreen mode, and both light and dark themes without creating editable fake geometry.
- [x] Prevent shared Markdown editor sticky chrome from colliding with fixed navigation and
  measured sticky form/action footers across page, modal, and fullscreen contexts.
- [x] Add interactive source-preserving Markdown tables with Editor/Source/Preview modes,
  row/column selection and structural actions, keyboard navigation, drag reordering, alignment,
  natural sorting, TSV/CSV clipboard exchange, table-safe typed wiki-link labels, and accessible
  mobile controls.
- [x] Refine interactive Markdown tables with Obsidian-like rectangular cell selection, adaptive
  Delete/Backspace/Cut semantics, edge-only add controls, Pointer Events row/column reordering,
  shared column geometry, a keyboard-accessible context menu, and one Editor-mode gutter number
  per table block.
- [x] Integrate interactive Markdown tables visually into the editor: remove card-like chrome and
  anonymous CSS table cells, keep empty rows stable, use content-based widths and quiet edge
  controls, and prevent vertical arrow navigation from skipping ordinary lines across a table.
- [x] Recover stable Markdown-table editing after the visual integration: keep every semantic row
  on its own CodeMirror source line, make empty cells directly editable without page-scroll jumps,
  constrain adaptive columns and edge controls to the editor viewport, protect structural pipes,
  keep the final body row, and cover bidirectional cell selection and single-step column insertion.
- [x] Remove the Markdown delimiter from the rendered line geometry, show an explicit caret and
  active state for empty table cells, and keep the first ordinary line after a table aligned with
  its CodeMirror gutter number.
- [x] Stabilize table-cell input across browsers: keep page scroll fixed while typing, show a
  source-position caret in populated and empty cells, replace the delimiter with a measured
  zero-height block, and protect the blank Markdown terminator that keeps following prose outside
  the table in Editor and Preview.
- [x] Eliminate the remaining cross-browser table interaction drift: keep repeated input and the
  cleared-cell caret in the addressed cell, move drag controls outside editable marks, give every
  row and column a distinct reachable handle with pickup/drop feedback, and suppress ordinary
  CodeMirror selection artifacts during rectangular cell drag.
- [x] Keep horizontal navigation inside pseudo-rendered Markdown tables on the owning page's
  current position by scrolling the rendered target cell instead of hidden source geometry.
- [x] Keep outer horizontal table arrows inside the pseudo-rendered grid instead of letting the
  browser move the caret into zero-height Markdown structure and jump the owning page upward.
- [x] Keep vertical navigation between pseudo-rendered table rows on the owning page's current
  position by scrolling the rendered target cell instead of hidden source geometry.
- [x] Keep ArrowDown entry from the ordinary line above a pseudo-rendered table from scrolling the
  owning page to hidden Markdown source geometry.
- [x] Establish invariant-driven Markdown-table regression coverage for forbidden caret positions,
  redirected input, navigation recovery, rectangular and cross-boundary selections, varied cell
  content, and single blinking-cursor rendering.
- [x] Harden every Markdown-editor interaction around tables with exhaustive mixed text/table
  selection, theme-aware native highlighting, cell and boundary navigation, whitespace editing,
  deletion, line breaks, indentation, modifiers, hotkeys, IME, clipboard, and multi-selection
  regression matrices.
- [x] Restore readable green-tinted selection in both Markdown Editor and Source modes without
  geometric table-selection artifacts or duplicate layers.
- [x] Keep the Markdown table caret to one normal cell-line height when ArrowLeft moves from a
  right empty cell into a left empty cell in headers and body rows.
- [x] Make ArrowUp from the top-left Markdown table cell deterministic and directionally correct
  for empty and populated cells, every table shape, and the exact visible line above the table.
- [x] Add balanced horizontal insets around pseudo-rendered Markdown tables without breaking
  viewport containment, controls, caret, or selection geometry.
- [x] Restrict Markdown table terminator protection to the final empty line at document EOF and
  keep all lines after a table normally editable when later content exists.
- [x] Move the admin-only Markdown editor theme out of the global stylesheet so CodeMirror,
  interactive tables, and editor styling stay lazy without raising the initial-bundle budget.
- [x] Restore the missing top and inline-end outer borders of pseudo-rendered Markdown tables.
- [x] Restore row/column drag-and-drop hit-area alignment in Markdown tables and cover every
  supported pickup, target, selection, pointer, boundary, cancellation, and undo/redo scenario.
- [x] Make Markdown table edge-add controls use the complete table boundary while preserving
  row/column drag hit areas and table geometry.
- [x] Make Markdown presentation decoration tests force a complete public CodeMirror parse instead
  of depending on the shared background-parser time budget.
- [x] Add a compact Markdown table header/body delimiter on the existing header-cell boundary
  without reintroducing hidden source-row height, shifting controls, or changing document flow.
- [x] Make Markdown presentation tests commit their forced public CodeMirror parse through a pure
  editor-state update so parser timing cannot make the suite intermittent.
- [ ] Make the Markdown table editor JSDOM interaction and invariant suites deterministic without
  relying on background parsing or viewport timing, and eliminate the leaked Jest worker reported
  by full frontend test runs.
- [x] Keep the caret in the same Markdown table cell after deleting or replacing all of its
  content, with a complete regression matrix for cell positions, source forms, input paths,
  selection state, scrolling, and undo/redo.
- [x] Keep Markdown search/replace in the editor's sticky header stack and theme its focus and
  checkbox states with the site's green accent across authoring modes and fullscreen.

### Other tasks

- [ ] Split monorepo into separate repos: front, back, infra.
- [x] UI localisation
- [x] Database localisation
- [ ] Migrate from Makefile to Just
- [x] Move complex logic out of Makefiles into dedicated script folders (`scripts/`, `frontend/scripts/`, `infra/scripts/`); keep Makefiles as thin wrappers that only call Bash scripts or nested Makefiles.
- [x] Refactor project scripts so `make <command>` fully prepares and runs tests, linters, checkers, and similar commands without manual setup (start required Docker services, prepare data, and run other prerequisites as needed).
- [x] Cache on API get methods + cache invalidation on changes
- [x] Background cache warm
- [ ] Evaluate/migrate TaskIQ results to a durable backend when durable task history/auditing is needed.
- [ ] Filestorage service for files in MinIO with moderators(and admins)-only access
- [x] docker infra should be hotswap: no 502 errors caused by service restart lag (change docker-compose if its not possible)
- [x] Add public changelog/updates page.
- [ ] Add RSS/Atom feeds for published articles and matrix updates.
- [ ] Add lightweight subscription channel for new articles, matrix items, and courses.
- [ ] Add public roadmap page for site/product development.
- [ ] Add link for published articles and matrix items from admin panel.

## Bugs

- [ ] Fix initial bundle big size.
- [x] Search does not work in "table" view mode (false positive; covered by frontend regression test)
- [x] Resource search is suboptimal (optimized through existing PostgreSQL pg_trgm support)
- [x] Production public UI QA
  - [x] Make the active `ru/en` language switch green instead of blue, matching the competency matrix active controls.
  - [x] Make the "to question" button on the competency matrix detail page green, consistent with the existing project button style.
  - [x] Localise the date-range filter placeholder: Russian may stay day-month-year format, but English should use a clearer US-style `mm.dd.yyyy` format.
  - [x] Add comfortable left and right padding to article text in the public articles list.
  - [x] Make the active article reaction state green instead of blue.
  - [x] On article detail pages, visually separate the back button from tags and make it green.
  - [x] Make the articles filter search button green.
  - [x] Prevent the English `Login` button text from wrapping as `Log` / `in`, so the header does not shift when switching languages.
  - [x] Move the `Folders` side-panel toggle to the left, replace the text button with an icon-only side-panel toggle whose icon reflects open/closed state, and add a simple open/close animation.
  - [x] Restyle the articles side panel so folders and articles read as a tree: reduce the default article background contrast, use hover background for articles, increase article indentation inside folders, and consider cohesive tree connector glyphs.
  - [x] Fix the sitemap page title overlapping the header.
  - [x] Show the list of published articles on the sitemap page.
  - [x] Remove the former public biography/contact surface from the unauthenticated site.
- [x] Production admin UI QA
  - [x] Make the logout control borderless: red text only, separated from the username by a vertical `|` delimiter.
  - [x] Prevent the English `Logout` button text from wrapping as `Log` / `out`.
  - [x] Make the add competency matrix question button green and move it inline after search.
  - [x] Make `published only` toggles green when enabled in admin matrix and article workspaces.
  - [x] Simplify admin actions for matrix questions and articles: use one actions dropdown in list rows and edit detail pages instead of several inline buttons.
  - [x] Make the admin `add article` control and article statistics navigation/action styling consistent with the admin UI.
  - [x] Move article statistics out of the public articles page and keep it in a dedicated admin page.
  - [x] Hide folders and filters when opening an article detail page.
  - [x] Fix Toast UI editor styling in dark theme so editing text and preview text remain readable and do not blend into the background.
  - [x] Fix the external resources modal: the Russian `add` button overflows the form, and both it and the save button should be green.
  - [x] Clarify which created external resource context field is Russian and which is English in the competency matrix question form.
  - [ ] query `?page=n` passed in article public detail page (from list). It shouldn't.

## Refactoring

- [ ] Rename `interview_expected_answer` / `interviewExpectedAnswer` everywhere to
  `interview_answer_explanation` / `interviewAnswerExplanation`, including the database,
  migrations, backend contracts, API schemas, frontend models, tests, and Agent Access.
- [x] Simplify BootstrapRenderer
- [x] Add pre-commit hooks (ruff, mypy, pytest)
- [x] Move CLI to a separate entry point (from main.py)
- [x] Use GradeEnum in API and core layer.
- [x] Rewrite NewType as regular classes.
- [x] Unite use-cases into a single class (separated by domain).
- [ ] Unite all repositories to the "unit of work" pattern.
- [ ] Fix taskiq not used imports of tasks from subpackages.
- [x] Move ResponseCacheKeyBuilder.build to target.
- [x] Move ResponseCachePayloadCodec to BaseModel.
- [x] Refactor core exceptions to inherit only from `Exception`/domain exception bases and move
  `verbose_http_exceptions` mapping to the Litestar entrypoint layer.
- [ ] Remove application-level id generators and rely on database-generated identifiers.
- [ ] Move functions from endpoints (to response classes or to other classes)
- [ ] Refactor core use cases to remove every private helper method: keep orchestration in public
  use-case methods, move entity invariants to domain schemas/value objects, and move shared
  cross-use-case behavior to domain services.
- [ ] Refactor localized read-facing core contracts so projected entities carry language-neutral
  fields such as `title`, `name`, and `content` instead of parallel `*_ru` / `*_en` fields; select
  the requested localization before constructing read models while keeping write/persistence
  translation contracts explicit where both languages are required.
- [ ] Add upgrade and downgrade migration coverage for revision
  `0004_add_backend_owned_file_metadata`.
- [ ] Move articles to personal web site 
- [ ] Prepare repository split
  - [x] Move Angular serving into a frontend-owned Docker image
  - [x] Keep infrastructure nginx as the edge reverse proxy
  - [x] Move root AGENTS.md rules to backend and frontend
  - [x] Move backend, frontend, and infrastructure into separate repositories
  - [x] Configure independent image publishing for backend and frontend
  - [x] Update deployment workflow to consume published images from the infrastructure repository
