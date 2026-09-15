import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


ARTICLES = "articles__article_model"
TAGS = "articles__tag_model"
ARTICLE_TAGS = "articles__article_to_tag_secondary_model"
ARTICLE_DAILY_ANALYTICS = "articles__article_daily_analytics_model"
ARTICLE_REACTIONS = "articles__article_reaction_model"
CONTACTS = "contacts__contact_me_model"
RESUMES = "resumes__resume_model"
CM_SHEETS = "competency_matrix__competency_matrix_sheet_model"
CM_SECTIONS = "competency_matrix__competency_matrix_section_model"
CM_SUBSECTIONS = "competency_matrix__competency_matrix_subsection_model"
CM_ITEMS = "competency_matrix__competency_matrix_item_model"
CM_RESOURCES = "competency_matrix__external_resource_model"
CM_QUEUED = "competency_matrix__queued_question_model"
CM_RESOURCE_LINKS = "competency_matrix__resource_to_item_secondary_model"

type ColumnSpec = tuple[str, sa.types.TypeEngine[Any]]
type DependentIndex = tuple[str, str]
type ForeignKeySpec = tuple[str, tuple[str, ...], str, tuple[str, ...], str | None]
type UniqueConstraintSpec = tuple[str, str, tuple[str, ...]]


ID_TABLES = (
    ARTICLES,
    TAGS,
    ARTICLE_TAGS,
    ARTICLE_DAILY_ANALYTICS,
    ARTICLE_REACTIONS,
    CONTACTS,
    RESUMES,
    CM_SHEETS,
    CM_SECTIONS,
    CM_SUBSECTIONS,
    CM_ITEMS,
    CM_RESOURCES,
    CM_QUEUED,
    CM_RESOURCE_LINKS,
)

INTEGER_ID_TABLES = (
    TAGS,
    ARTICLE_TAGS,
    ARTICLE_DAILY_ANALYTICS,
    ARTICLE_REACTIONS,
    RESUMES,
    CM_SHEETS,
    CM_SECTIONS,
    CM_SUBSECTIONS,
    CM_ITEMS,
    CM_RESOURCES,
    CM_QUEUED,
    CM_RESOURCE_LINKS,
)

UUID_ID_TABLES = (ARTICLES, CONTACTS)

UPGRADE_COLUMNS: Mapping[str, tuple[ColumnSpec, ...]] = {
    ARTICLES: (("id", sa.String(length=32)),),
    TAGS: (("id", sa.String(length=32)),),
    ARTICLE_TAGS: (
        ("id", sa.String(length=32)),
        ("article_id", sa.String(length=32)),
        ("tag_id", sa.String(length=32)),
    ),
    ARTICLE_DAILY_ANALYTICS: (
        ("id", sa.String(length=32)),
        ("article_id", sa.String(length=32)),
    ),
    ARTICLE_REACTIONS: (
        ("id", sa.String(length=32)),
        ("article_id", sa.String(length=32)),
    ),
    CONTACTS: (("id", sa.String(length=32)),),
    RESUMES: (("id", sa.String(length=32)),),
    CM_SHEETS: (("id", sa.String(length=32)),),
    CM_SECTIONS: (
        ("id", sa.String(length=32)),
        ("sheet_id", sa.String(length=32)),
    ),
    CM_SUBSECTIONS: (
        ("id", sa.String(length=32)),
        ("section_id", sa.String(length=32)),
    ),
    CM_ITEMS: (
        ("id", sa.String(length=32)),
        ("subsection_id", sa.String(length=32)),
    ),
    CM_RESOURCES: (("id", sa.String(length=32)),),
    CM_QUEUED: (("id", sa.String(length=32)),),
    CM_RESOURCE_LINKS: (
        ("id", sa.String(length=32)),
        ("item_id", sa.String(length=32)),
        ("resource_id", sa.String(length=32)),
    ),
}

DOWNGRADE_COLUMNS: Mapping[str, tuple[ColumnSpec, ...]] = {
    ARTICLES: (("id", sa.UUID()),),
    TAGS: (("id", sa.BigInteger()),),
    ARTICLE_TAGS: (
        ("id", sa.BigInteger()),
        ("article_id", sa.UUID()),
        ("tag_id", sa.BigInteger()),
    ),
    ARTICLE_DAILY_ANALYTICS: (
        ("id", sa.BigInteger()),
        ("article_id", sa.UUID()),
    ),
    ARTICLE_REACTIONS: (
        ("id", sa.BigInteger()),
        ("article_id", sa.UUID()),
    ),
    CONTACTS: (("id", sa.UUID()),),
    RESUMES: (("id", sa.BigInteger()),),
    CM_SHEETS: (("id", sa.BigInteger()),),
    CM_SECTIONS: (
        ("id", sa.BigInteger()),
        ("sheet_id", sa.BigInteger()),
    ),
    CM_SUBSECTIONS: (
        ("id", sa.BigInteger()),
        ("section_id", sa.BigInteger()),
    ),
    CM_ITEMS: (
        ("id", sa.BigInteger()),
        ("subsection_id", sa.BigInteger()),
    ),
    CM_RESOURCES: (("id", sa.BigInteger()),),
    CM_QUEUED: (("id", sa.BigInteger()),),
    CM_RESOURCE_LINKS: (
        ("id", sa.BigInteger()),
        ("item_id", sa.BigInteger()),
        ("resource_id", sa.BigInteger()),
    ),
}

DEPENDENT_INDEXES: tuple[DependentIndex, ...] = (
    (RESUMES, "resumes_resume_author_updated_id_idx"),
    (CM_SHEETS, "cm_sheet_priority_idx"),
    (CM_SECTIONS, "cm_section_sheet_en_idx"),
    (CM_SECTIONS, "cm_section_sheet_ru_idx"),
    (CM_SECTIONS, "cm_section_sheet_priority_idx"),
    (CM_SUBSECTIONS, "cm_subsection_section_en_idx"),
    (CM_SUBSECTIONS, "cm_subsection_section_ru_idx"),
    (CM_SUBSECTIONS, "cm_subsection_section_priority_idx"),
    (CM_ITEMS, "cmi_subsection_status_grade_idx"),
    (CM_ITEMS, "cmi_workspace_status_published_at_idx"),
    (CM_ITEMS, "cmi_workspace_subsection_status_grade_idx"),
)

DEPENDENT_UNIQUE_CONSTRAINTS: tuple[UniqueConstraintSpec, ...] = (
    (
        ARTICLE_DAILY_ANALYTICS,
        "articles_daily_analytics_article_date_source_uniq",
        ("article_id", "date", "source_category"),
    ),
    (
        ARTICLE_REACTIONS,
        "articles_reaction_article_voter_uniq",
        ("article_id", "article_scoped_voter_hash"),
    ),
    (ARTICLE_TAGS, "articles_article_tag_uniq", ("article_id", "tag_id")),
    (CM_SECTIONS, "cm_section_sheet_name_ru_uniq", ("sheet_id", "name_ru")),
    (CM_SECTIONS, "cm_section_sheet_name_en_uniq", ("sheet_id", "name_en")),
    (CM_SUBSECTIONS, "cm_subsection_section_name_ru_uniq", ("section_id", "name_ru")),
    (CM_SUBSECTIONS, "cm_subsection_section_name_en_uniq", ("section_id", "name_en")),
    (CM_RESOURCE_LINKS, "cm_resource_item_uniq", ("item_id", "resource_id")),
)

DEPENDENT_FOREIGN_KEYS: tuple[ForeignKeySpec, ...] = (
    (ARTICLE_DAILY_ANALYTICS, ("article_id",), ARTICLES, ("id",), "CASCADE"),
    (ARTICLE_REACTIONS, ("article_id",), ARTICLES, ("id",), "CASCADE"),
    (ARTICLE_TAGS, ("article_id",), ARTICLES, ("id",), "CASCADE"),
    (ARTICLE_TAGS, ("tag_id",), TAGS, ("id",), "CASCADE"),
    (CM_SECTIONS, ("sheet_id",), CM_SHEETS, ("id",), "CASCADE"),
    (CM_SUBSECTIONS, ("section_id",), CM_SECTIONS, ("id",), "CASCADE"),
    (CM_ITEMS, ("subsection_id",), CM_SUBSECTIONS, ("id",), "RESTRICT"),
    (CM_RESOURCE_LINKS, ("item_id",), CM_ITEMS, ("id",), "CASCADE"),
    (CM_RESOURCE_LINKS, ("resource_id",), CM_RESOURCES, ("id",), "CASCADE"),
)


def upgrade() -> None:
    connection = op.get_bind()
    id_maps: dict[str, dict[object, object]] = {
        table_name: _uuid_to_hex_id_map(connection=connection, table_name=table_name)
        for table_name in UUID_ID_TABLES
    }
    id_maps.update(
        {
            table_name: _generated_hex_id_map(connection=connection, table_name=table_name)
            for table_name in INTEGER_ID_TABLES
        },
    )

    _add_temp_columns(column_specs=UPGRADE_COLUMNS)
    _populate_id_columns(connection=connection, id_maps=id_maps)
    _populate_fk_columns(
        connection=connection,
        mappings=(
            (ARTICLE_DAILY_ANALYTICS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_REACTIONS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_TAGS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_TAGS, "tag_id", id_maps[TAGS]),
            (CM_SECTIONS, "sheet_id", id_maps[CM_SHEETS]),
            (CM_SUBSECTIONS, "section_id", id_maps[CM_SECTIONS]),
            (CM_ITEMS, "subsection_id", id_maps[CM_SUBSECTIONS]),
            (CM_RESOURCE_LINKS, "item_id", id_maps[CM_ITEMS]),
            (CM_RESOURCE_LINKS, "resource_id", id_maps[CM_RESOURCES]),
        ),
    )
    _drop_dependent_objects(connection=connection)
    _swap_columns(column_specs=UPGRADE_COLUMNS, id_server_defaults=_hex_id_defaults())
    _create_dependent_objects()
    _create_hex_only_indexes()


def downgrade() -> None:
    connection = op.get_bind()
    id_maps: dict[str, dict[object, object]] = {
        table_name: _hex_to_uuid_id_map(connection=connection, table_name=table_name)
        for table_name in UUID_ID_TABLES
    }
    id_maps.update(
        {
            table_name: _dense_integer_id_map(connection=connection, table_name=table_name)
            for table_name in INTEGER_ID_TABLES
        },
    )

    _add_temp_columns(column_specs=DOWNGRADE_COLUMNS)
    _populate_id_columns(connection=connection, id_maps=id_maps)
    _populate_fk_columns(
        connection=connection,
        mappings=(
            (ARTICLE_DAILY_ANALYTICS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_REACTIONS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_TAGS, "article_id", id_maps[ARTICLES]),
            (ARTICLE_TAGS, "tag_id", id_maps[TAGS]),
            (CM_SECTIONS, "sheet_id", id_maps[CM_SHEETS]),
            (CM_SUBSECTIONS, "section_id", id_maps[CM_SECTIONS]),
            (CM_ITEMS, "subsection_id", id_maps[CM_SUBSECTIONS]),
            (CM_RESOURCE_LINKS, "item_id", id_maps[CM_ITEMS]),
            (CM_RESOURCE_LINKS, "resource_id", id_maps[CM_RESOURCES]),
        ),
    )
    _drop_hex_only_indexes()
    _drop_dependent_objects(connection=connection)
    _swap_columns(
        column_specs=DOWNGRADE_COLUMNS,
        id_server_defaults=_integer_sequence_defaults(connection=connection, id_maps=id_maps),
    )
    _create_dependent_objects()


def _uuid_to_hex_id_map(*, connection: Connection, table_name: str) -> dict[object, object]:
    return {
        value: _uuid_hex(value=value)
        for value in _column_values(connection=connection, table_name=table_name, column_name="id")
    }


def _hex_to_uuid_id_map(*, connection: Connection, table_name: str) -> dict[object, object]:
    return {
        value: uuid.UUID(hex=str(value))
        for value in _column_values(connection=connection, table_name=table_name, column_name="id")
    }


def _generated_hex_id_map(*, connection: Connection, table_name: str) -> dict[object, object]:
    return {
        value: uuid.uuid4().hex
        for value in _column_values(connection=connection, table_name=table_name, column_name="id")
    }


def _dense_integer_id_map(*, connection: Connection, table_name: str) -> dict[object, object]:
    return {
        value: index
        for index, value in enumerate(
            _column_values(connection=connection, table_name=table_name, column_name="id"),
            start=1,
        )
    }


def _column_values(
    *,
    connection: Connection,
    table_name: str,
    column_name: str,
) -> list[object]:
    table = _core_table(table_name=table_name, column_names=(column_name,))
    rows = connection.execute(sa.select(table.c[column_name]).order_by(table.c[column_name]))
    return list(rows.scalars())


def _uuid_hex(*, value: object) -> str:
    if isinstance(value, uuid.UUID):
        return value.hex
    return uuid.UUID(str(value)).hex


def _add_temp_columns(*, column_specs: Mapping[str, tuple[ColumnSpec, ...]]) -> None:
    for table_name, columns in column_specs.items():
        for column_name, type_ in columns:
            op.add_column(
                table_name,
                sa.Column(_temp_column(column_name=column_name), type_, nullable=True),
            )


def _populate_id_columns(
    *,
    connection: Connection,
    id_maps: Mapping[str, Mapping[object, object]],
) -> None:
    for table_name, id_map in id_maps.items():
        _populate_temp_column(
            connection=connection,
            table_name=table_name,
            column_name="id",
            value_map=id_map,
        )


def _populate_fk_columns(
    *,
    connection: Connection,
    mappings: Iterable[tuple[str, str, Mapping[object, object]]],
) -> None:
    for table_name, column_name, value_map in mappings:
        _populate_temp_column(
            connection=connection,
            table_name=table_name,
            column_name=column_name,
            value_map=value_map,
        )


def _populate_temp_column(
    *,
    connection: Connection,
    table_name: str,
    column_name: str,
    value_map: Mapping[object, object],
) -> None:
    temp_column = _temp_column(column_name=column_name)
    table = _core_table(table_name=table_name, column_names=(column_name, temp_column))
    for old_value, new_value in value_map.items():
        connection.execute(
            sa.update(table)
            .where(table.c[column_name] == old_value)
            .values({temp_column: new_value}),
        )


def _drop_dependent_objects(*, connection: Connection) -> None:
    for table_name, index_name in DEPENDENT_INDEXES:
        op.drop_index(index_name, table_name=table_name)
    for table_name, constraint_name, _columns in DEPENDENT_UNIQUE_CONSTRAINTS:
        op.drop_constraint(constraint_name, table_name, type_="unique")
    _drop_reflected_foreign_keys(connection=connection)
    _drop_reflected_primary_keys(connection=connection)


def _drop_reflected_foreign_keys(*, connection: Connection) -> None:
    fk_tables = tuple({table_name for table_name, *_items in DEPENDENT_FOREIGN_KEYS})
    for table_name in fk_tables:
        table = _reflect_table(connection=connection, table_name=table_name)
        for constraint in table.foreign_key_constraints:
            if isinstance(constraint.name, str):
                op.drop_constraint(constraint.name, table_name, type_="foreignkey")


def _drop_reflected_primary_keys(*, connection: Connection) -> None:
    for table_name in ID_TABLES:
        table = _reflect_table(connection=connection, table_name=table_name)
        if isinstance(table.primary_key.name, str):
            op.drop_constraint(table.primary_key.name, table_name, type_="primary")


def _swap_columns(
    *,
    column_specs: Mapping[str, tuple[ColumnSpec, ...]],
    id_server_defaults: Mapping[str, sa.DefaultClause],
) -> None:
    for table_name, columns in column_specs.items():
        for column_name, _type in columns:
            op.drop_column(table_name, column_name)
        for column_name, type_ in columns:
            op.alter_column(
                table_name,
                _temp_column(column_name=column_name),
                new_column_name=column_name,
                existing_type=type_,
                nullable=False,
                server_default=(
                    id_server_defaults.get(table_name) if column_name == "id" else None
                ),
            )


def _hex_id_defaults() -> dict[str, sa.DefaultClause]:
    return {table_name: _hex_id_default() for table_name in ID_TABLES}


def _hex_id_default() -> sa.DefaultClause:
    return sa.DefaultClause(
        sa.func.replace(sa.cast(sa.func.gen_random_uuid(), sa.String()), "-", ""),
    )


def _integer_sequence_defaults(
    *,
    connection: Connection,
    id_maps: Mapping[str, Mapping[object, object]],
) -> dict[str, sa.DefaultClause]:
    defaults: dict[str, sa.DefaultClause] = {}
    for table_name in INTEGER_ID_TABLES:
        max_id = max((int(str(value)) for value in id_maps[table_name].values()), default=0)
        sequence = sa.Sequence(_sequence_name(table_name=table_name), start=max_id + 1)
        connection.execute(sa.schema.CreateSequence(sequence, if_not_exists=True))
        defaults[table_name] = sa.DefaultClause(sequence.next_value())
    return defaults


def _sequence_name(*, table_name: str) -> str:
    return f"{table_name}_id_seq"


def _create_dependent_objects() -> None:
    for table_name in ID_TABLES:
        op.create_primary_key(None, table_name, ["id"])
    for table_name, columns, remote_table, remote_columns, ondelete in DEPENDENT_FOREIGN_KEYS:
        op.create_foreign_key(
            None,
            table_name,
            remote_table,
            list(columns),
            list(remote_columns),
            ondelete=ondelete,
        )
    for table_name, constraint_name, columns in DEPENDENT_UNIQUE_CONSTRAINTS:
        op.create_unique_constraint(constraint_name, table_name, list(columns))
    _create_dependent_indexes()


def _create_dependent_indexes() -> None:
    op.create_index(
        "resumes_resume_author_updated_id_idx",
        RESUMES,
        ["author_username", sa.column("updated_at").desc(), sa.column("id").desc()],
        unique=False,
    )
    op.create_index("cm_sheet_priority_idx", CM_SHEETS, ["priority", "id"], unique=False)
    op.create_index(
        "cm_section_sheet_en_idx",
        CM_SECTIONS,
        ["sheet_id", "name_en", "id"],
        unique=False,
    )
    op.create_index(
        "cm_section_sheet_ru_idx",
        CM_SECTIONS,
        ["sheet_id", "name_ru", "id"],
        unique=False,
    )
    op.create_index(
        "cm_section_sheet_priority_idx",
        CM_SECTIONS,
        ["sheet_id", "priority", "id"],
        unique=False,
    )
    op.create_index(
        "cm_subsection_section_en_idx",
        CM_SUBSECTIONS,
        ["section_id", "name_en", "id"],
        unique=False,
    )
    op.create_index(
        "cm_subsection_section_ru_idx",
        CM_SUBSECTIONS,
        ["section_id", "name_ru", "id"],
        unique=False,
    )
    op.create_index(
        "cm_subsection_section_priority_idx",
        CM_SUBSECTIONS,
        ["section_id", "priority", "id"],
        unique=False,
    )
    op.create_index(
        "cmi_subsection_status_grade_idx",
        CM_ITEMS,
        ["subsection_id", "publish_status", "grade", "id"],
        unique=False,
    )
    op.create_index(
        "cmi_workspace_status_published_at_idx",
        CM_ITEMS,
        ["publish_status", sa.column("published_at").desc().nullslast(), "id"],
        unique=False,
    )
    op.create_index(
        "cmi_workspace_subsection_status_grade_idx",
        CM_ITEMS,
        ["subsection_id", "publish_status", "grade", "id"],
        unique=False,
    )


def _create_hex_only_indexes() -> None:
    for index_name, name_column in (
        ("articles_tag_active_name_ru_id_idx", "name_ru"),
        ("articles_tag_active_name_en_id_idx", "name_en"),
    ):
        op.create_index(
            index_name,
            TAGS,
            [sa.func.lower(sa.column(name_column)).label(f"active_{name_column}_lower"), "id"],
            unique=False,
            postgresql_include=(
                "name_ru",
                "name_en",
                "slug",
                "deleted_at",
                "created_at",
                "updated_at",
            ),
            postgresql_where=sa.column("deleted_at").is_(None),
        )


def _drop_hex_only_indexes() -> None:
    op.drop_index("articles_tag_active_name_ru_id_idx", table_name=TAGS)
    op.drop_index("articles_tag_active_name_en_id_idx", table_name=TAGS)


def _reflect_table(*, connection: Connection, table_name: str) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(table_name, metadata, autoload_with=connection)


def _core_table(*, table_name: str, column_names: Iterable[str]) -> sa.TableClause:
    return sa.table(table_name, *(sa.column(column_name) for column_name in column_names))


def _temp_column(*, column_name: str) -> str:
    return f"__next_{column_name}"
