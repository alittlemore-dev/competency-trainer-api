from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, post
from verbose_http_exceptions import status

from core.contacts.use_cases import ContactsUseCase
from core.generators import HexUuidIdGenerator
from entrypoints.litestar.api.contacts.schemas import ContactMeRequest
from entrypoints.litestar.api.parameters import api_json_body
from infra.config.settings import settings


class ContactsApiController(Controller):
    path = "/contacts"
    tags = ["contacts"]

    @post(
        "",
        status_code=status.HTTP_204_NO_CONTENT,
        description="Create a contact request.",
    )
    async def contact_me_request(
        self,
        id_generator: FromDishka[HexUuidIdGenerator],
        data: Annotated[
            ContactMeRequest,
            api_json_body(
                title="Contact request",
                description="Public contact form payload.",
                examples=(
                    {
                        "name": "Dmitriy Lunev",
                        "email": "example@mail.ru",
                        "telegram": "@alm_dmitriy_dev",
                        "message": "I would like to discuss a project.",
                    },
                ),
            ),
        ],
        use_case: FromDishka[ContactsUseCase],
    ) -> None:
        if not settings.app.contact_requests_enabled:
            return
        await use_case.create_contact_me_request(
            form=data.to_schema(contact_me_id=id_generator.get_next()),
        )


api_router = DishkaRouter("", route_handlers=[ContactsApiController])
