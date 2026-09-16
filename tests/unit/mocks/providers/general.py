import uuid
from datetime import UTC, datetime

from dishka import Provider, Scope, provide

from core.generators import HexUuidIdGenerator
from core.types import IntId

test_current_datetime = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)


class MockGeneralProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_current_datetime(self) -> datetime:
        return test_current_datetime

    def __init__(self, uuid_: uuid.UUID | None = None, hex_uuid: str | None = None) -> None:
        super().__init__()
        self.uuid_ = uuid_ or uuid.uuid4()
        self.hex_uuid = hex_uuid or self.uuid_.hex

    @provide(scope=Scope.APP)
    async def provide_random_uuid(self) -> uuid.UUID:
        return self.uuid_

    @provide(scope=Scope.APP)
    async def provide_hex_uuid_id_generator(self) -> HexUuidIdGenerator:
        return HexUuidIdGenerator(generator=lambda: self.hex_uuid)

    @provide(scope=Scope.APP)
    async def provide_random_int(self) -> IntId:
        return IntId(int(self.uuid_.hex[:15], 16))
