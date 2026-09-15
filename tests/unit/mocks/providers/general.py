import uuid

from dishka import Provider, Scope, provide

from core.generators import HexUuidIdGenerator
from core.types import IntId


class MockGeneralProvider(Provider):
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
