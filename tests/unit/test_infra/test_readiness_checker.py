from unittest.mock import AsyncMock, Mock

import pytest

from infra.healthcheck import ReadinessChecker, ReadinessCheckError
from infra.s3.clients import S3ClientBundle


class TestReadinessChecker:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.session = Mock()
        self.session.execute = AsyncMock()
        self.valkey = Mock()
        self.valkey.ping = AsyncMock()
        self.internal_s3_client = Mock()
        self.internal_s3_client.head_bucket = AsyncMock()
        self.public_s3_client = Mock()
        self.checker = ReadinessChecker(
            session=self.session,
            valkey=self.valkey,
            s3_clients=S3ClientBundle(
                internal=self.internal_s3_client,
                public=self.public_s3_client,
            ),
        )

    async def test_check_uses_internal_s3_client_for_media_bucket(self) -> None:
        await self.checker.check()

        self.internal_s3_client.head_bucket.assert_awaited_once_with(Bucket="media")

    async def test_check_fails_when_s3_bucket_check_fails(self) -> None:
        self.internal_s3_client.head_bucket.side_effect = RuntimeError("S3 is unavailable")

        with pytest.raises(ReadinessCheckError):
            await self.checker.check()
