from collections.abc import Sequence
from importlib import import_module
from inspect import getmembers, isclass, iscoroutinefunction

from performance.query_plans.models import StorageMethod

STORAGE_MODULE_NAMES = (
    "infra.postgresql.storages.agent_access",
    "infra.postgresql.storages.auth",
    "infra.postgresql.storages.competency_matrix",
    "infra.postgresql.storages.contacts",
    "infra.postgresql.storages.articles",
    "infra.postgresql.storages.users",
)


def discover_storage_methods() -> tuple[StorageMethod, ...]:
    return discover_storage_methods_from_modules(module_names=STORAGE_MODULE_NAMES)


def discover_storage_methods_from_modules(
    *,
    module_names: Sequence[str],
) -> tuple[StorageMethod, ...]:
    discovered_methods: list[StorageMethod] = []
    for module_name in module_names:
        module = import_module(module_name)
        for storage_class_name, storage_class in getmembers(module, isclass):
            if not is_concrete_database_storage(
                storage_class=storage_class,
                module_name=module_name,
                storage_class_name=storage_class_name,
            ):
                continue
            discovered_methods.extend(
                StorageMethod(
                    storage_class=storage_class_name,
                    method_name=method_name,
                    module_name=module_name,
                )
                for method_name, method in getmembers(storage_class, iscoroutinefunction)
                if not method_name.startswith("_")
                if getattr(method, "__isabstractmethod__", False) is False
            )
    return tuple(
        sorted(
            discovered_methods,
            key=lambda method: (method.storage_class, method.method_name),
        ),
    )


def is_concrete_database_storage(
    *,
    storage_class: type[object],
    module_name: str,
    storage_class_name: str,
) -> bool:
    return (
        storage_class.__module__ == module_name
        and storage_class_name.endswith("DatabaseStorage")
        and getattr(storage_class, "__abstractmethods__", frozenset()) == frozenset()
    )
