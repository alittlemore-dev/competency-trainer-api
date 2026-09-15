from collections.abc import Iterable
from typing import Any


class CollectionsHelper:
    def pluck(self, items: Iterable[Any], attr: str) -> list[Any]:
        return [getattr(item, attr) for item in items]

    def ids(self, items: Iterable[Any]) -> list[Any]:
        return self.pluck(items=items, attr="id")

    def slugs(self, items: Iterable[Any]) -> list[str]:
        return self.pluck(items=items, attr="slug")

    def names_en(self, items: Iterable[Any]) -> list[str]:
        return self.pluck(items=items, attr="name_en")

    def sheet_keys(self, items: Iterable[Any]) -> list[str]:
        return self.pluck(items=items, attr="key")
