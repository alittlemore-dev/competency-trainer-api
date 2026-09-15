from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "interview_expected_answer_ru",
        new_column_name="interview_answer_explanation_ru",
    )
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "interview_expected_answer_en",
        new_column_name="interview_answer_explanation_en",
    )


def downgrade() -> None:
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "interview_answer_explanation_ru",
        new_column_name="interview_expected_answer_ru",
    )
    op.alter_column(
        "competency_matrix__competency_matrix_item_model",
        "interview_answer_explanation_en",
        new_column_name="interview_expected_answer_en",
    )
