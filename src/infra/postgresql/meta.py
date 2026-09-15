from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infra.config.settings import settings
from infra.postgresql.query_monitoring import install_query_monitoring

engine = create_async_engine(
    settings.database.url.get_secret_value(),
    pool_pre_ping=settings.database.pool_pre_ping,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
)
install_query_monitoring(
    engine=engine,
    enabled=settings.database.log_query_metrics,
    slow_query_log_threshold_ms=settings.database.slow_query_log_threshold_ms,
    statement_max_length=settings.database.slow_query_log_statement_max_length,
)

sessionmaker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=settings.database.expire_on_commit,
)
