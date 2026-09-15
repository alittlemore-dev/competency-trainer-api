from hashlib import sha256

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

items = sa.table(
    "competency_matrix__competency_matrix_item_model",
    sa.column("id", sa.String()),
    sa.column("question_ru", sa.String()),
    sa.column("question_en", sa.String()),
    sa.column("question_ru_fingerprint", sa.LargeBinary(length=32)),
    sa.column("question_en_fingerprint", sa.LargeBinary(length=32)),
)
queued_questions = sa.table(
    "competency_matrix__queued_question_model",
    sa.column("id", sa.String()),
    sa.column("question", sa.String()),
    sa.column("question_fingerprint", sa.LargeBinary(length=32)),
)


def question_fingerprint_digest(question: str) -> bytes:
    fingerprint = " ".join(question.split()).casefold()
    return sha256(fingerprint.encode()).digest()


def upgrade() -> None:
    op.add_column(
        "competency_matrix__competency_matrix_item_model",
        sa.Column("question_ru_fingerprint", sa.LargeBinary(length=32), nullable=True),
    )
    op.add_column(
        "competency_matrix__competency_matrix_item_model",
        sa.Column("question_en_fingerprint", sa.LargeBinary(length=32), nullable=True),
    )
    op.add_column(
        "competency_matrix__queued_question_model",
        sa.Column("question_fingerprint", sa.LargeBinary(length=32), nullable=True),
    )
    connection = op.get_bind()
    item_rows = connection.execute(
        sa.select(items.c.id, items.c.question_ru, items.c.question_en),
    ).mappings()
    item_updates = [
        {
            "item_id": row["id"],
            "ru_fingerprint": question_fingerprint_digest(row["question_ru"]),
            "en_fingerprint": question_fingerprint_digest(row["question_en"]),
        }
        for row in item_rows
    ]
    if item_updates:
        connection.execute(
            sa.update(items)
            .where(items.c.id == sa.bindparam("item_id"))
            .values(
                question_ru_fingerprint=sa.bindparam("ru_fingerprint"),
                question_en_fingerprint=sa.bindparam("en_fingerprint"),
            ),
            item_updates,
        )
    queue_rows = connection.execute(
        sa.select(queued_questions.c.id, queued_questions.c.question),
    ).mappings()
    queue_updates = [
        {
            "question_id": row["id"],
            "fingerprint": question_fingerprint_digest(row["question"]),
        }
        for row in queue_rows
    ]
    if queue_updates:
        connection.execute(
            sa.update(queued_questions)
            .where(queued_questions.c.id == sa.bindparam("question_id"))
            .values(question_fingerprint=sa.bindparam("fingerprint")),
            queue_updates,
        )
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "question_ru_fingerprint",
        existing_type=sa.LargeBinary(length=32),
        nullable=False,
    )
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "question_en_fingerprint",
        existing_type=sa.LargeBinary(length=32),
        nullable=False,
    )
    op.alter_column(
        "competency_matrix__queued_question_model",
        "question_fingerprint",
        existing_type=sa.LargeBinary(length=32),
        nullable=False,
    )
    op.create_index(
        "cmi_question_en_fingerprint_idx",
        "competency_matrix__competency_matrix_item_model",
        ["question_en_fingerprint"],
        unique=False,
    )
    op.create_index(
        "cmi_question_ru_fingerprint_idx",
        "competency_matrix__competency_matrix_item_model",
        ["question_ru_fingerprint"],
        unique=False,
    )
    op.create_index(
        "cm_queued_question_fingerprint_idx",
        "competency_matrix__queued_question_model",
        ["question_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "cm_queued_question_fingerprint_idx",
        table_name="competency_matrix__queued_question_model",
    )
    op.drop_index(
        "cmi_question_ru_fingerprint_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_index(
        "cmi_question_en_fingerprint_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_column("competency_matrix__queued_question_model", "question_fingerprint")
    op.drop_column(
        "competency_matrix__competency_matrix_item_model",
        "question_en_fingerprint",
    )
    op.drop_column(
        "competency_matrix__competency_matrix_item_model",
        "question_ru_fingerprint",
    )
