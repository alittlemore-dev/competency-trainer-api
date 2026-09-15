from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.enums import RoleEnum
from core.auth.password_hashers import PasswordHasher
from infra.config.loggers import logger
from infra.ioc.container import container
from infra.postgresql.models import UserModel


async def create_admin_command(username: str, password: str) -> None:
    async with container() as request_container:
        hasher = await request_container.get(PasswordHasher)
        session = await request_container.get(AsyncSession)
        hashed_password = hasher.hash_password(password)
        try:
            stmt = (
                insert(UserModel)
                .values(
                    username=username,
                    password_hash=hashed_password,
                    role=RoleEnum.OWNER,
                    is_active=True,
                )
                .on_conflict_do_nothing(index_elements=["username"])
            )
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError:
            msg = "Database error"
            logger.exception(msg)
            await session.rollback()
        except Exception as exc:  # noqa: BLE001
            msg = f"Internal error: {exc!s}"
            logger.exception(msg)
        else:
            msg = "Owner created successfully."
            logger.info(msg)
