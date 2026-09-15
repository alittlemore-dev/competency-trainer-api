from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "person_details_author_birthday_item_idx",
        "knowledge__person_details_model",
        ["author_username", "birthday_month", "birthday_day", "item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "person_details_author_birthday_item_idx", table_name="knowledge__person_details_model"
    )
