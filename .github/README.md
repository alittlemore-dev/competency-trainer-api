# Competency Trainer

[🇷🇺 Russian version](./README_RU.md)

An engineering knowledge platform that combines a competency matrix, bilingual publishing, and a
protected editorial workspace.

## Technologies

| Category | Technologies |
|----------|--------------|
| Coverage | ![coverage-backend](./badges/coverage-backend.svg) |
| Backend | ![python](./badges/python.svg) ![litestar](./badges/litestar.svg) ![async](./badges/async.svg) ![pydantic](./badges/pydantic.svg) ![dishka](./badges/dishka.svg) ![taskiq](./badges/taskiq.svg) ![paseto](./badges/paseto.svg) ![argon2](./badges/argon2.svg) ![mcp](./badges/mcp.svg) |
| Database | ![postgresql](./badges/postgresql.svg) ![sqlalchemy](./badges/sqlalchemy.svg) ![alembic](./badges/alembic.svg) |
| Cache | ![valkey](./badges/valkey.svg) |
| Testing | ![pytest](./badges/pytest.svg) |
| DevOps | ![docker](./badges/docker.svg) ![nginx](./badges/nginx.svg) ![minio](./badges/minio.svg) ![docker-compose](./badges/docker-compose.svg) |
| Quality | ![ruff](./badges/ruff.svg) ![mypy](./badges/mypy.svg) ![bandit](./badges/bandit.svg) ![pip-audit](./badges/pip-audit.svg) ![trivy](./badges/trivy.svg) ![hadolint](./badges/hadolint.svg) ![dockle](./badges/dockle.svg) ![vulture](./badges/vulture.svg) |
| Logging | ![structlog](./badges/structlog.svg) ![ecs-logging](./badges/ecs-logging.svg) ![sentry](./badges/sentry.svg) |
| Architecture | ![clean-architecture](./badges/clean-architecture.svg) ![type-safe](./badges/type-safe.svg) |
| Tools | ![uv](./badges/uv.svg) ![granian](./badges/granian.svg) |
| CI/CD | ![github-actions](./badges/github-actions.svg) ![dependabot](./badges/dependabot.svg) |

## Features

- A bilingual competency matrix with priority-ordered learning paths, search, grid and table views,
  detailed Q&A pages, and linked resources
- RU/EN article publishing with folders, tags, search, filters, and SSR public pages
- Privacy-conscious engagement analytics with view counters, source categories, and anonymous
  reactions
- A role-based workspace for managing articles, competency questions, publishing, and the editorial
  team
- Restricted AI-agent access through a private mTLS interface, with MCP limited to draft operations

## Getting started

```bash
cp .env.example .env
make install
make run-local
make tests-fast
make build
```
