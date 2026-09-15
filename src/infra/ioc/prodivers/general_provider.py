import secrets
import uuid

from dishka import Provider, Scope, provide

from core.generators import HexUuidIdGenerator, generate_uuid4_hex
from core.types import IntId


class GeneralProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_hex_uuid_id_generator(self) -> HexUuidIdGenerator:
        return HexUuidIdGenerator(generator=generate_uuid4_hex)

    @provide(scope=Scope.REQUEST, cache=False)
    async def provide_random_uuid(self) -> uuid.UUID:
        return uuid.uuid4()

    @provide(scope=Scope.REQUEST, cache=False)
    async def provide_random_int(self) -> IntId:
        value = IntId(int(uuid.uuid4().hex[:15], 16))
        sign = secrets.choice([-1, 1])
        return IntId(value * sign)
