from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "files__file_model",
        sa.Column(
            "original_sha256",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        "files_file_namespace_purpose_original_sha256_idx",
        "files__file_model",
        ["namespace", "purpose", "original_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "files_file_namespace_purpose_original_sha256_idx",
        table_name="files__file_model",
    )
    op.drop_column("files__file_model", "original_sha256")
