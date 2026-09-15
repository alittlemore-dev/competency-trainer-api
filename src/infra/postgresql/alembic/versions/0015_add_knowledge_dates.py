from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

ITEM_TABLE = "knowledge__knowledge_item_model"
KIND_ENUM_NAME = "knowledge_item_kind_enum"
KIND_TEXT_COLUMN = "kind_text"
KIND_INDEXES = (
    "knowledge_items_author_kind_name_id_idx",
    "knowledge_items_author_kind_updated_id_idx",
)


def replace_kind_enum(
    *,
    source_enum: postgresql.ENUM,
    target_enum: postgresql.ENUM,
) -> None:
    item_table = sa.table(
        ITEM_TABLE,
        sa.column("kind", source_enum),
        sa.column(KIND_TEXT_COLUMN, sa.String(length=255)),
    )
    op.add_column(
        ITEM_TABLE,
        sa.Column(KIND_TEXT_COLUMN, sa.String(length=255), nullable=True),
    )
    op.get_bind().execute(
        item_table.update().values(
            {KIND_TEXT_COLUMN: sa.cast(item_table.c.kind, sa.String(length=255))},
        ),
    )
    for index_name in KIND_INDEXES:
        op.drop_index(index_name, table_name=ITEM_TABLE)
    op.drop_column(ITEM_TABLE, "kind")
    source_enum.drop(op.get_bind(), checkfirst=False)
    target_enum.create(op.get_bind(), checkfirst=False)
    op.add_column(
        ITEM_TABLE,
        sa.Column(
            "kind",
            postgresql.ENUM(
                *target_enum.enums,
                name=KIND_ENUM_NAME,
                create_type=False,
            ),
            nullable=True,
        ),
    )
    item_table = sa.table(
        ITEM_TABLE,
        sa.column(
            "kind",
            postgresql.ENUM(
                *target_enum.enums,
                name=KIND_ENUM_NAME,
                create_type=False,
            ),
        ),
        sa.column(KIND_TEXT_COLUMN, sa.String(length=255)),
    )
    op.get_bind().execute(
        item_table.update().values(
            {"kind": sa.cast(item_table.c.kind_text, target_enum)},
        ),
    )
    op.drop_column(ITEM_TABLE, KIND_TEXT_COLUMN)
    op.alter_column(ITEM_TABLE, "kind", nullable=False)
    op.create_index(
        "knowledge_items_author_kind_name_id_idx",
        ITEM_TABLE,
        [
            "author_username",
            "kind",
            sa.func.lower(sa.column("display_name")).label("display_name_lower"),
            "id",
        ],
        unique=False,
    )
    op.create_index(
        "knowledge_items_author_kind_updated_id_idx",
        ITEM_TABLE,
        [
            "author_username",
            "kind",
            sa.column("updated_at").desc(),
            sa.column("id").desc(),
        ],
        unique=False,
    )


def upgrade() -> None:
    replace_kind_enum(
        source_enum=postgresql.ENUM(
            "PERSON",
            name=KIND_ENUM_NAME,
            create_type=False,
        ),
        target_enum=postgresql.ENUM(
            "DATE",
            "PERSON",
            name=KIND_ENUM_NAME,
            create_type=False,
        ),
    )
    op.create_index(
        "knowledge_items_display_name_trgm_idx",
        ITEM_TABLE,
        [sa.func.lower(sa.column("display_name")).label("display_name_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"display_name_lower_trgm": "gin_trgm_ops"},
    )
    op.create_table(
        "knowledge__date_details_model",
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            sa.and_(
                sa.column("day").between(1, 31),
                sa.column("month").between(1, 12),
                sa.or_(
                    sa.column("year").is_(None),
                    sa.column("year").between(1, 9999),
                ),
                sa.column("day")
                <= sa.case(
                    (sa.column("month").in_((1, 3, 5, 7, 8, 10, 12)), 31),
                    (sa.column("month").in_((4, 6, 9, 11)), 30),
                    (sa.column("year").is_(None), 29),
                    (
                        sa.or_(
                            sa.column("year") % 400 == 0,
                            sa.and_(
                                sa.column("year") % 4 == 0,
                                sa.column("year") % 100 != 0,
                            ),
                        ),
                        29,
                    ),
                    else_=28,
                ),
                sa.or_(
                    sa.column("year").is_(None),
                    sa.func.make_date(
                        sa.column("year"),
                        sa.column("month"),
                        sa.column("day"),
                    )
                    <= sa.func.current_date(),
                ),
            ),
            name="date_details_calendar_check",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "author_username"],
            [
                "knowledge__knowledge_item_model.id",
                "knowledge__knowledge_item_model.author_username",
            ],
            name="date_details_item_author_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.UniqueConstraint("item_id", "author_username", name="date_details_id_author_uniq"),
    )
    op.create_index(
        "date_details_author_calendar_item_idx",
        "knowledge__date_details_model",
        ["author_username", "month", "day", "item_id"],
        unique=False,
    )
    op.create_table(
        "knowledge__date_person_model",
        sa.Column("date_item_id", sa.String(length=32), nullable=False),
        sa.Column("person_item_id", sa.String(length=32), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["date_item_id", "author_username"],
            [
                "knowledge__date_details_model.item_id",
                "knowledge__date_details_model.author_username",
            ],
            name="date_people_date_author_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_item_id", "author_username"],
            [
                "knowledge__person_details_model.item_id",
                "knowledge__person_details_model.author_username",
            ],
            name="date_people_person_author_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("date_item_id", "person_item_id"),
    )
    op.create_index(
        "date_people_author_date_person_idx",
        "knowledge__date_person_model",
        ["author_username", "date_item_id", "person_item_id"],
        unique=False,
    )
    op.create_index(
        "date_people_author_person_date_idx",
        "knowledge__date_person_model",
        ["author_username", "person_item_id", "date_item_id"],
        unique=False,
    )


def downgrade() -> None:
    date_enum = postgresql.ENUM(
        "DATE",
        "PERSON",
        name=KIND_ENUM_NAME,
        create_type=False,
    )
    items = sa.table(
        ITEM_TABLE,
        sa.column("kind", date_enum),
    )
    op.get_bind().execute(items.delete().where(items.c.kind == "DATE"))
    op.drop_index(
        "date_people_author_person_date_idx",
        table_name="knowledge__date_person_model",
    )
    op.drop_index(
        "date_people_author_date_person_idx",
        table_name="knowledge__date_person_model",
    )
    op.drop_table("knowledge__date_person_model")
    op.drop_index(
        "date_details_author_calendar_item_idx",
        table_name="knowledge__date_details_model",
    )
    op.drop_table("knowledge__date_details_model")
    op.drop_index(
        "knowledge_items_display_name_trgm_idx",
        table_name=ITEM_TABLE,
    )
    replace_kind_enum(
        source_enum=date_enum,
        target_enum=postgresql.ENUM(
            "PERSON",
            name=KIND_ENUM_NAME,
            create_type=False,
        ),
    )
