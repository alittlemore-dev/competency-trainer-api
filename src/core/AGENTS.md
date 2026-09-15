# Core Layer Instructions

These rules apply to backend core code under `src/core/**/*.py`.

## Strict Import Rules

- Core may import only the Python standard library and `core.*`. Do not import third-party
  packages, outer layers, infrastructure config, or logging, including in exception modules.
- Keep domain invariants and parser rules in core. Receive infrastructure-owned settings and
  configurable policy through explicit schemas, parameters, or IOC wiring; their source remains
  `src/infra/config/constants.py`.

## Shared Core Files

Shared files can be used across all domains.

```text
schemas.py      # Shared domain schemas
enums.py        # Shared enums
types.py        # Shared type aliases
exceptions.py   # Shared domain exceptions
generators.py   # Shared generators
```

## Domain Structure

Common files per domain in `src/core/<domain>/`. Not all files are required.

```text
schemas.py              # domain models (dataclasses or class with init dunder method)
use_cases.py            # Business logic - concrete use cases only, no ABC/Protocol/base inheritance.
storages.py             # Storage ABC - repository pattern (SQLAlchemy, Mongo, etc.)
clients.py              # External client ABCs (S3-compatible object clients, HTTP clients, etc.)
exceptions.py           # Domain exceptions
parsers.py              # Domain parsers
readers.py              # Reader interfaces
enums.py                # Domain enumerations
types.py                # Domain type aliases or NewType
services.py             # Domain services - shared business logic, uses in use cases
event_dispatchers.py    # Domain event/reporting interfaces; concrete transports live outside core
```

## Domain Rules

- New core code must be domain dataclasses, value objects, use cases, services, interfaces, exceptions, or generators.
- Use cases must be concrete standalone classes. Do not add abstract use-case interfaces,
  `Protocol` contracts, base use-case classes, or inheritance between use cases.
- Use-case constructor attributes may contain injected collaborating abstractions and class-based
  generators or services. A class-based generator for random values or values derived from supplied
  data is a valid collaborator; do not create a class whose only purpose is to provide the current
  time. Pass operation-specific concrete values, especially current timestamps and policy/config
  data, explicitly to public use-case methods, and never inject callable factories for them.
- Use cases contain orchestration, straightforward field checks, storage reads, and DB-derived
  decisions. Do not add private/static helpers or collection-transformation loops. Put entity
  checks on domain objects, construction/conversion in schema classmethods, and shared behavior
  in domain services.
- When an operation has both a target entity identifier and a current actor identifier, the public
  use-case method must read both domain entities when actor permissions are relevant, then call a
  public permission/check method on the actor or target domain schema. Do not encode actor-vs-target
  authorization rules as raw string comparisons in the use case.
- Use cases must not depend on or call other use cases. When the logic belongs to only one
  use case, keep it in that use case and inject storage abstractions directly. Put shared
  cross-use-case business logic in the relevant domain `services.py` as a concrete service.
- Keep core abstraction names and method parameters technology-neutral. Express a synchronization
  intent with a name such as `lock`; do not expose adapter implementation terms such as
  `for_update` in a storage or client contract.
- Group ordinary service configuration values, such as namespaces, rules, limits, and batch sizes,
  in a typed configuration schema and inject that schema through a `config` attribute. Keep service
  attributes outside `config` for collaborating abstractions only.
- Core exceptions must express domain failures and inherit only from `Exception` or project domain
  exception bases that themselves inherit from `Exception`. Litestar/HTTP representation belongs in
  the Litestar entrypoint layer, where core exceptions should be mapped to
  `verbose_http_exceptions`.
- Put parser input/output schemas, parser rule objects, and value objects in `schemas.py`; put
  parser classes in `parsers.py`; put reader interfaces in `readers.py`; put parser/domain errors
  in `exceptions.py`. Do not create feature-specific modules when an existing standard domain file
  type fits the object.
- Do not log secrets, password hashes, tokens, raw credentials, or other sensitive values.
