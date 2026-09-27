import sqlalchemy as sa
from alembic import op


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    item_name = "competency_matrix__competency_matrix_item_model"
    subsection_name = "competency_matrix__competency_matrix_subsection_model"
    section_name = "competency_matrix__competency_matrix_section_model"
    item = sa.table(
        item_name,
        sa.column("subsection_id", sa.String(length=32)),
        sa.column("sheet_id", sa.String(length=32)),
    )
    subsection = sa.table(
        subsection_name,
        sa.column("id", sa.String(length=32)),
        sa.column("section_id", sa.String(length=32)),
    )
    section = sa.table(
        section_name,
        sa.column("id", sa.String(length=32)),
        sa.column("sheet_id", sa.String(length=32)),
    )
    op.add_column(
        item_name,
        sa.Column("sheet_id", sa.String(length=32), nullable=True),
    )
    connection = op.get_bind()
    sheet_id = (
        sa.select(section.c.sheet_id)
        .select_from(subsection.join(section, subsection.c.section_id == section.c.id))
        .where(subsection.c.id == item.c.subsection_id)
        .scalar_subquery()
    )
    connection.execute(sa.update(item).values(sheet_id=sheet_id))
    op.alter_column(item_name, "sheet_id", nullable=False)
    op.drop_index(
        op.f("ix_competency_matrix__competency_matrix_item_model_slug"),
        table_name=item_name,
    )
    op.create_unique_constraint(
        "cm_item_sheet_slug_uniq",
        item_name,
        ["sheet_id", "slug"],
    )
    op.create_foreign_key(
        "cm_item_sheet_id_fkey",
        item_name,
        "competency_matrix__competency_matrix_sheet_model",
        ["sheet_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    item_name = "competency_matrix__competency_matrix_item_model"
    item = sa.table(
        item_name,
        sa.column("slug", sa.String(length=255)),
        sa.column("sheet_id", sa.String(length=32)),
    )
    duplicate_slug = op.get_bind().scalar(
        sa.select(item.c.slug).group_by(item.c.slug).having(sa.func.count() > 1).limit(1)
    )
    if duplicate_slug is not None:
        message = "Cannot restore global slug uniqueness while sheets share a slug"
        raise RuntimeError(message)
    op.drop_constraint("cm_item_sheet_id_fkey", item_name, type_="foreignkey")
    op.drop_constraint("cm_item_sheet_slug_uniq", item_name, type_="unique")
    op.create_index(
        op.f("ix_competency_matrix__competency_matrix_item_model_slug"),
        item_name,
        ["slug"],
        unique=True,
    )
    op.drop_column(item_name, "sheet_id")
