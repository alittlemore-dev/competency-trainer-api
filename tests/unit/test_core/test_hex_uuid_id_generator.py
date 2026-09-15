import re

from core import generators
from core.generators import generate_uuid4_hex


def test_hex_uuid_id_generator_returns_lowercase_32_char_hex_id() -> None:
    generator_cls = getattr(generators, "HexUuidIdGenerator", None)

    assert generator_cls is not None
    value = generator_cls(generator=generate_uuid4_hex).get_next()

    assert re.fullmatch(r"[0-9a-f]{32}", value) is not None


def test_hex_uuid_id_generator_returns_unique_ids() -> None:
    generator_cls = getattr(generators, "HexUuidIdGenerator", None)

    assert generator_cls is not None
    generator = generator_cls(generator=generate_uuid4_hex)

    assert generator.get_next() != generator.get_next()
