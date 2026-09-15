from dishka import make_async_container

from infra.ioc.registry import get_providers

container = make_async_container(*get_providers())
