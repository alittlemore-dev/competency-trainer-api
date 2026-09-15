from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


role_enum = postgresql.ENUM(
    "ANON",
    "USER",
    "MODERATOR",
    "ADMIN",
    "OWNER",
    name="role_enum",
    create_type=False,
)
users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String(length=255)),
    sa.column("role", role_enum),
)
items = sa.table(
    "competency_matrix__competency_matrix_item_model",
    sa.column("suggested_by_username", sa.String(length=255)),
)
queued_questions = sa.table(
    "competency_matrix__queued_question_model",
    sa.column("suggested_by_username", sa.String(length=255)),
)


def upgrade() -> None:
    op.add_column(
        "competency_matrix__competency_matrix_item_model",
        sa.Column("suggested_by_username", sa.String(length=255), nullable=True),
    )
    op.drop_constraint(
        op.f("competency_matrix__queued_question_m_suggested_by_username_fkey"),
        "competency_matrix__queued_question_model",
        type_="foreignkey",
    )
    connection = op.get_bind()
    owner_usernames = tuple(
        connection.scalars(
            sa.select(users.c.username).where(users.c.role == "OWNER"),
        ),
    )
    if len(owner_usernames) != 1:
        msg = "Exactly one owner is required to backfill matrix question attribution"
        raise RuntimeError(msg)
    owner_username = owner_usernames[0]
    connection.execute(
        sa.update(items).values(suggested_by_username=owner_username),
    )
    connection.execute(
        sa.update(queued_questions)
        .where(queued_questions.c.suggested_by_username.is_(None))
        .values(suggested_by_username=owner_username),
    )
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "suggested_by_username",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )
    op.alter_column(
        "competency_matrix__queued_question_model",
        "suggested_by_username",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "competency_matrix__queued_question_model",
        "suggested_by_username",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )
    existing_user = sa.exists(
        sa.select(users.c.username).where(
            users.c.username == queued_questions.c.suggested_by_username,
        ),
    )
    op.get_bind().execute(
        sa.update(queued_questions)
        .where(~existing_user)
        .values(suggested_by_username=None),
    )
    op.create_foreign_key(
        op.f("competency_matrix__queued_question_m_suggested_by_username_fkey"),
        "competency_matrix__queued_question_model",
        "auth__user_model",
        ["suggested_by_username"],
        ["username"],
        ondelete="SET NULL",
    )
    op.drop_column("competency_matrix__competency_matrix_item_model", "suggested_by_username")
