from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from valkey.asyncio import Valkey

from infra.config.constants import constants
from infra.config.loggers import logger
from infra.s3.clients import S3ClientBundle


class ReadinessCheckError(Exception):
    pass


@dataclass(kw_only=True, slots=True)
class ReadinessChecker:
    session: AsyncSession
    valkey: Valkey
    s3_clients: S3ClientBundle

    async def check(self) -> None:
        await self._check_postgres()
        await self._check_valkey()
        await self._check_s3()

    async def _check_postgres(self) -> None:
        try:
            await self.session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            self._fail("PostgreSQL readiness check failed", exc)

    async def _check_valkey(self) -> None:
        try:
            await self.valkey.ping()
        except Exception as exc:  # noqa: BLE001
            self._fail("Valkey readiness check failed", exc)

    async def _check_s3(self) -> None:
        try:
            await self.s3_clients.internal.head_bucket(Bucket=constants.minio_buckets.media)
        except Exception as exc:  # noqa: BLE001
            self._fail("S3 readiness check failed", exc)

    def _fail(self, message: str, exc: Exception) -> NoReturn:
        logger.warning(message, exc_info=True)
        raise ReadinessCheckError from exc
