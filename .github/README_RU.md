# Мой сайт

[🇺🇸 English version](./README.md)

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

> [!NOTE]
> Покрытие backend генерируется pytest (Python).

Инженерный сайт с публичной case-study страницей, обновлениями, матрицей компетенций,
локализованными статьями и защищёнными рабочими областями для управления контентом.

## 📖 Документация

- [Идея проекта](../docs/idea.md)  
- [Что нужно сделать](../docs/TODO.md)

## 📂 Структура проекта

```
competency-trainer/
├── src/            # Исходный код приложения
├── tests/          # Backend-тесты (pytest)
├── performance/    # Сценарии и отчёты проверки планов PostgreSQL
├── scripts/        # Backend quality, test, image и MCP helpers
├── .env.example    # Пример переменных окружения
├── .env.test       # Безопасные переменные для тестового окружения
├── docker-compose.test.yml
└── Dockerfile
```

## ✨ Возможности

- Матрица компетенций: локализованные листы, разделы и подразделы с управляемым приоритетом, поиск, табличная сетка, детальные ответы, публичные SEO-страницы вопросов, пикер и сортировка структуры в админке, внешние ресурсы
- Статьи: RU/EN-контент, папки, теги, поиск, фильтры по датам/тегам, управление публикацией и SSR-страницы публичных статей
- Защищённая панель владельца/администратора/модератора: создание, редактирование, публикация и снятие с публикации статей и вопросов матрицы, плюс управление командой, где администраторы управляют модераторами, а единственный владелец имеет полный доступ к команде
- Приватная аналитика статей: публичные счётчики просмотров, вовлечённые просмотры, категории источников и анонимные реакции
- Публичная case-study страница «как устроен сайт» про архитектуру, качество и эксплуатацию
- Публичная страница обновлений с milestone-изменениями сайта
- Локализация интерфейса и контента на русском и английском языках
- PASETO-аутентификация для защищённого режима владельца/администратора/модератора
  со скользящими, очищаемыми и управляемыми в админке серверными сесиями и
  блокировкой неактивных аккаунтов
- Приватный Agent-контур через WireGuard и nginx mTLS, смонтированный в основном Litestar
  приложении, и локальный stdio MCP bridge с пятью tools. Публичный listener скрывает внутренний
  route и удаляет поддельный certificate header, а mTLS-listener пропускает только семь точных REST
  операций. Раздельные сертификаты, scopes, закрытые routes и серверный Draft-контроль исключают
  публикацию, generic CRUD, произвольный fetch, shell, SQL и Docker-операции. Упрощённая композиция
  осознанно оставляет общими с backend процесс, роль БД, секреты и контур доступности.

## 🚀 Запуск

Создайте локальную конфигурацию, установите зависимости, запустите быстрые тесты и соберите образ
сервиса:

```bash
cp .env.example .env
make install
make tests-fast
make build
```

Единый локальный и production runtime находится в соседнем
[infra-репозитории](https://github.com/alittlemore-dev/infra). При соседнем расположении checkout
один раз выполните `make -C ../infra dev-trust`, затем запускайте `make -C ../infra dev`.

## Локальный MCP bridge

1. Запустить общий стек через `make -C ../infra dev` и один раз зарегистрировать клиентский CSR в
   `/admin-panel/workspace/agent-clients`.
2. Скопировать `.env.agent-bridge.example` в `.env.agent-bridge` и указать абсолютные пути к CA,
   выданному сертификату и приватному ключу.
3. Перезапустить Codex в этом репозитории. Checked-in конфигурация автоматически запустит stdio
   bridge с пятью tools; вручную экспортировать переменные не нужно.

Генерация сертификатов, desktop rotation и полная модель безопасности описаны в
[Agent Access](../docs/agent-access.md).

## ⚙️ Важные ссылки

Общий локальный edge создаётся соседним infra-репозиторием.

- API: `https://alittlemore.localhost/api/competency/`
- API liveness: `https://alittlemore.localhost/api/competency/healthcheck`
- API readiness: `https://alittlemore.localhost/api/competency/healthcheck/ready`
- Документация API: `https://alittlemore.localhost/api/competency/docs`
- OpenAPI спецификация: `https://alittlemore.localhost/api/competency/docs/openapi.json`

Внутренние web-панели доступны только через host-level WireGuard и nginx-порты,
привязанные к `VPN_BIND_ADDRESS`:

- MinIO Console: `http://<VPN_BIND_ADDRESS>:18081`
- Databasus: `http://<VPN_BIND_ADDRESS>:18082`
- Agent API: `https://agent.<APP_DOMAIN>:18083/internal/agent/v1` (WireGuard и активный клиентский
  сертификат; MCP bridge запускается локально через stdio)

Операционный контракт описан в документации infra-репозитория:
[WireGuard](https://github.com/alittlemore-dev/infra/blob/main/docs/wireguard-internal-access.md)
и [production deployment](https://github.com/alittlemore-dev/infra/blob/main/docs/production-deploy.md).

## 🧪 Тесты

```bash
make tests-fast                 # backend unit-тесты; backend test DB не нужна
make tests                      # полный набор backend-тестов
make test-backend               # backend unit + integration + serial migrations
make test-backend-unit          # unit-тесты backend, DB не нужна
make test-backend-integration   # интеграционные тесты backend, test DB готовится автоматически
make tests-coverage             # отчёт покрытия backend
make query-plans-realistic      # обязательный main gate: реалистичные данные, планы + latency
make query-plans-stress         # ручной большой профиль: строгие планы, latency как observation
```

Основной CI вызывает reusable query-plan workflow с профилем `realistic` и timeout 20 минут.
Отдельный ручной workflow **Query-plan profiles** принимает calibration-прогон `realistic` или
`stress`, использует timeout 45 минут и публикует артефакты `query-plan-reports-<profile>`.

Backend pytest targets запускаются с явным числом pytest-xdist воркеров по физическим CPU-ядрам,
без `-n auto`. Для serial-режима задайте `BACKEND_PYTEST_WORKERS=0` или `1`; любое значение больше
`1` принудительно задаёт точное число воркеров. Unit-тесты идут без test DB; integration-тесты
клонируют мигрированную template DB текущего запуска в отдельные PostgreSQL базы на worker, а
Alembic migration-тесты остаются serial на базовой test DB.
