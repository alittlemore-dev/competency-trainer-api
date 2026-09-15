# Frontend Instructions

These rules apply to all frontend-owned application code, configuration, tooling, and documentation
under `frontend/`. Shared repository infrastructure and configuration must live outside `frontend/`.

## Stack

- Angular 22, standalone components only
- Angular hybrid rendering with `@angular/ssr`: public article, site-build case-study, updates, and competency matrix question routes use SSR, interactive protected routes remain CSR/hydrated Angular.
- Keep Angular framework packages, Angular CLI/build tooling, and `angular-eslint` on the same Angular major.
- SCSS for styles
- Bootstrap 5 via `styles/main.scss`
- Jest via `jest-preset-angular` for tests
- Node.js production runtime for the frontend Docker image; do not reintroduce a frontend-owned nginx runtime unless a new design explicitly asks for it.

## TypeScript

- Keep strict typing and the repository lint/format configuration; use `unknown` and narrowing
  rather than `any` for unknown shapes.
- Explicit return types on public methods and functions
- Prefer `interface` over `type` for object shapes

## Naming

- Files: `kebab-case` (e.g. `matrix-question-card.component.ts`)
- Classes and interfaces: `PascalCase`
- Signals: noun only — `questions`, `loading`, `error` (not `questionsSignal`, not `isLoading$`)
- Observables: noun + `$` suffix — `questions$`
- Services: `PascalCase` + `Service` suffix

## Components

- `OnPush` change detection — no exceptions
- `inject()` over constructor injection
- Standalone only — no `NgModule`
- Keep business logic and complex transformations out of templates. Simple Angular control flow,
  property access, and presentation expressions may stay in the template; move reusable or
  non-obvious derivation to the component class or `computed()`.
- Semantic HTML. Accessibility attributes where meaningful (`aria-label`, `role`, etc.)
- Add co-located `.spec.ts` for new components and services unless the behavior is truly trivial.
- Treat public reading/detail views differently from management workspaces: keep detail pages focused
  on the content being read, and avoid showing list filters, tree navigation, bulk controls, or other
  workspace-only controls unless they are directly needed for the detail workflow.
- Icon-only controls must expose an accessible name and make their current state clear through icon,
  title, ARIA state, or surrounding context.
- Prefer an established shared custom form control when required product visuals or interaction
  logic cannot be implemented correctly with a native control. Otherwise use the native control.
  Custom controls must preserve native-grade accessibility, keyboard behavior, Angular Forms
  integration, validation, SSR safety, and CSP compatibility.
- When users only need format guidance, keep the native control and provide visible localized hints
  and titles instead of adding custom parsing.

## State

| Mechanism | Use |
|---|---|
| `signal()` | Mutable local component state |
| `computed()` | Derived values — never duplicated signal state |
| `effect()` | True side effects only (e.g. syncing to query params) |
| `toSignal()` | Converting `Observable` to signal for template consumption |
| Service state | Only when state is shared across multiple routed components |

## Notifications

- Transient app notifications must auto-dismiss within 5 seconds. Do not let success, error,
  validation, save, import/export, or other feedback toasts accumulate until the user manually
  closes them; persistent problems belong in inline/page-level error UI instead.

## HTTP

- Feature services inject `ApiClient` — never raw `HttpClient`
- Services return `Observable<T>` — no Promises
- Components consume via `toSignal()` or explicit `subscribe` with `DestroyRef` cleanup
- DTOs mapped to UI models explicitly when field names or shapes differ
- Sanitize any backend or user-provided Markdown/HTML before binding it with `[innerHTML]`; SSR paths must not depend on browser-only sanitizer APIs.
- Put reusable frontend upload helpers under `core/uploads/`, not `core/media/`; the latter matches
  a repository ignore pattern.
- Fetch protected private-file content through authenticated APIs as `Blob` data. Browser object
  URLs are short-lived capabilities: revoke superseded URLs and release all remaining URLs on
  errors, navigation, and component destruction; never persist or expose them as backend object
  URLs.
- Keep direct `localStorage` access in core services; feature components may use it only for local UI preferences and must cover that behavior with tests. All storage, `window`, `document.defaultView`, timer, analytics, reaction, upload, and DOM-download behavior must be guarded so public SSR detail pages can render without browser APIs.

## SSR and Browser APIs

- Treat SSR as a pure render path. Browser-only capabilities such as storage, crypto, DOM mutation,
  timers, analytics, reactions, downloads, uploads, and editor setup must be behind platform guards or
  injected browser-document accessors and must not run during server rendering.
- Browser capability helpers should fail closed: return `null`, skip work, or no-op when no browser
  context exists, and callers must handle that absence explicitly instead of assuming the browser is
  always available.
- When adding or changing storage-backed UI preferences, preserve browser persistence and add tests
  that prove the same code path does not touch browser-only APIs with a server-like document.

## Forms

- `FormControl<T>` and `FormGroup<T>` — always typed
- Single field -> `FormControl<T>`. Multiple related fields -> `FormGroup`
- Mark required form-field labels with
  `<span class="required-marker text-danger" aria-hidden="true">*</span>` and keep the control's
  native or component-level required semantics in sync. Do not append `(optional)` or localized
  equivalents to optional labels; the absence of the required marker communicates optionality.
- User-triggered saves, creates, updates, deletes, imports, exports, validation checks, and other
  state-changing or validation-gated actions must always produce explicit user feedback on every
  blocked, failed, and successful path. Do not silently return from invalid forms or skipped
  actions: show localized inline errors, notifications, visible disabled/loading states, route/tab
  focus, or another concrete cue that tells the user what happened and what to fix next.
- Admin forms with `formControlName` fields must apply the shared validation-state mechanism
  (`AdminControlValidationStateDirective` or the feature's equivalent) so every invalid touched
  `input`, `textarea`, and `select` receives visible invalid styling without one-off template gaps.
- Admin create/edit forms must register every unsaved authoring source with the shared admin
  unsaved-changes mechanism, including nested inline drafts and non-form state. Compare the current
  value with the last loaded or successfully saved baseline so a full manual revert is clean, guard
  modal close and route/browser exit paths, and exclude filters, search, sorting, preview controls,
  and export options that do not represent authored data.

## Comments

- Comment only on non-obvious constraints, workarounds, or invariants.

## Styles

- Prefer Bootstrap utilities and existing CSS variables before adding component SCSS.
- Component SCSS must stay focused on local layout/overrides, not global theme concerns.
- Add new colors through theme variables, not hardcoded component palettes.
- Keep action hierarchy consistent across public and admin UI. Primary create/save/edit actions may
  use the positive accent; destructive or publication-state-changing actions should usually be less
  visually dominant unless the surrounding design establishes a stronger pattern.

## Frontend Verification

- Use the existing Make targets for tests, lint, typecheck, format-check, security, and build as
  relevant to the change. Do not bypass them without explicit task authorization. Jest setup and
  runner options are defined in `frontend/jest.config.ts`; follow adjacent specs and test helpers.
- Check observable loading/error/empty/populated states, input/output interactions, API request
  contracts, and guard behavior where changed. Use rendered DOM and HTTP test responses rather
  than private state, arbitrary DOM nesting, source text, framework internals, dependency metadata,
  or exact editorial copy. Co-locate new behavioral specs with their component/service.
- Cover changed critical behavior; numerical coverage gates belong in test/CI configuration.
  Do not introduce an end-to-end framework without a project-level testing strategy decision.
- For integrated browser validation, use `make run` from the application repository root.
  Use a narrower fallback only when the stack is unavailable or the task requires it; explain the
  limitation and clean up temporary servers after verification.
- For SSR routing, server entrypoints, public-detail SEO, or transfer-cache changes, run the
  focused tests and `make -C frontend ssr-smoke` from the repository root.
