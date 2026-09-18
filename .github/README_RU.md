# Competency Trainer

[🇺🇸 English version](./README.md)

Инженерная база знаний, объединяющая матрицу компетенций, двуязычные публикации и защищённое
пространство для работы с контентом.

## Технологии

| Категория | Технологии |
|----------|------------|
| Покрытие | ![coverage-backend](./badges/coverage-backend.svg) |
| Backend | ![python](./badges/python.svg) ![litestar](./badges/litestar.svg) ![async](./badges/async.svg) ![pydantic](./badges/pydantic.svg) ![dishka](./badges/dishka.svg) ![taskiq](./badges/taskiq.svg) ![paseto](./badges/paseto.svg) ![argon2](./badges/argon2.svg) ![mcp](./badges/mcp.svg) |
| База данных | ![postgresql](./badges/postgresql.svg) ![sqlalchemy](./badges/sqlalchemy.svg) ![alembic](./badges/alembic.svg) |
| Кэш | ![valkey](./badges/valkey.svg) |
| Тестирование | ![pytest](./badges/pytest.svg) |
| DevOps | ![docker](./badges/docker.svg) ![nginx](./badges/nginx.svg) ![minio](./badges/minio.svg) ![docker-compose](./badges/docker-compose.svg) |
| Качество | ![ruff](./badges/ruff.svg) ![mypy](./badges/mypy.svg) ![bandit](./badges/bandit.svg) ![pip-audit](./badges/pip-audit.svg) ![trivy](./badges/trivy.svg) ![hadolint](./badges/hadolint.svg) ![dockle](./badges/dockle.svg) ![vulture](./badges/vulture.svg) |
| Логирование | ![structlog](./badges/structlog.svg) ![ecs-logging](./badges/ecs-logging.svg) ![sentry](./badges/sentry.svg) |
| Архитектура | ![clean-architecture](./badges/clean-architecture.svg) ![type-safe](./badges/type-safe.svg) |
| Инструменты | ![uv](./badges/uv.svg) ![granian](./badges/granian.svg) |
| CI/CD | ![github-actions](./badges/github-actions.svg) ![dependabot](./badges/dependabot.svg) |

## Возможности

- Двуязычная матрица компетенций с приоритетными траекториями обучения, поиском, табличным и
  сеточным представлениями, подробными Q&A-страницами и связанными материалами
- Публикация статей на русском и английском языках с папками, тегами, поиском, фильтрами и
  публичными SSR-страницами
- Бережная к приватности аналитика вовлечённости со счётчиками просмотров, категориями источников и
  анонимными реакциями
- Ролевое пространство для управления статьями, вопросами матрицы, публикацией и редакционной
  командой
- Ограниченный доступ для AI-агентов через приватный mTLS-интерфейс и MCP только для работы с
  черновиками

## Начало работы

```bash
cp .env.example .env
make install
make run-local
make tests-fast
make build
```
