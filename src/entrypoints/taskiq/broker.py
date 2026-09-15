from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from infra.config.constants import constants
from infra.config.settings import settings

broker = RedisStreamBroker(
    url=settings.valkey.get_url(db=constants.valkey.databases.taskiq_broker)
    .get_secret_value()
    .replace("valkey://", "redis://", 1),
    queue_name=constants.taskiq.queue_name,
    consumer_group_name=constants.taskiq.consumer_group_name,
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.valkey.get_url(db=constants.valkey.databases.taskiq_results)
        .get_secret_value()
        .replace("valkey://", "redis://", 1),
        keep_results=True,
        result_ex_time=settings.taskiq.result_expire_seconds,
        prefix_str=constants.taskiq.result_prefix,
    ),
)
