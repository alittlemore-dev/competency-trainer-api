from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _enum_types_by_name() -> dict[str, postgresql.ENUM]:
    return {
        "agent_client_status": postgresql.ENUM(
            "ACTIVE",
            "REVOKED",
            name="agent_client_status_enum",
            create_type=False,
        ),
        "agent_scope": postgresql.ENUM(
            "MATRIX_QUEUE_CLAIM",
            "MATRIX_CONTEXT_READ",
            "MATRIX_RESOURCES_READ",
            "MATRIX_DRAFT_CREATE",
            name="agent_scope_enum",
            create_type=False,
        ),
        "agent_action": postgresql.ENUM(
            "CLAIM_NEXT_MATRIX_QUESTION",
            "GET_MATRIX_AUTHORING_CONTEXT",
            "SEARCH_MATRIX_RESOURCES",
            "SAVE_MATRIX_QUESTION_DRAFT",
            "RELEASE_MATRIX_QUESTION_CLAIM",
            "ROTATE_AGENT_CERTIFICATE",
            "CONFIRM_AGENT_CERTIFICATE_ROTATION",
            name="agent_action_enum",
            create_type=False,
        ),
        "agent_audit_result": postgresql.ENUM(
            "SUCCESS",
            "REJECTED",
            "FAILED",
            name="agent_audit_result_enum",
            create_type=False,
        ),
    }


def upgrade() -> None:
    enum_types = _enum_types_by_name()
    for enum_type in enum_types.values():
        enum_type.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "agent_access__agent_client_model",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            enum_types["agent_client_status"],
            nullable=False,
        ),
        sa.Column(
            "scopes",
            postgresql.ARRAY(enum_types["agent_scope"]),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.func.replace(
                sa.cast(sa.func.gen_random_uuid(), sa.String()),
                "-",
                "",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "agent_client_name_lower_uniq",
        "agent_access__agent_client_model",
        [sa.func.lower(sa.column("name")).label("name_lower")],
        unique=True,
    )
    op.create_index(
        "agent_client_status_created_idx",
        "agent_access__agent_client_model",
        ["status", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "agent_access__agent_certificate_model",
        sa.Column("agent_client_id", sa.String(length=32), nullable=False),
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("serial_number", sa.String(length=64), nullable=False),
        sa.Column("certificate_pem", sa.Text(), nullable=False),
        sa.Column(
            "valid_from",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.func.replace(
                sa.cast(sa.func.gen_random_uuid(), sa.String()),
                "-",
                "",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_client_id"], ["agent_access__agent_client_model.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint_sha256"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_index(
        "agent_certificate_client_expiry_idx",
        "agent_access__agent_certificate_model",
        ["agent_client_id", "expires_at", "id"],
        unique=False,
    )
    op.create_index(
        "agent_certificate_revoked_expiry_idx",
        "agent_access__agent_certificate_model",
        ["revoked_at", "expires_at", "id"],
        unique=False,
    )
    op.create_table(
        "agent_access__matrix_question_claim_model",
        sa.Column("agent_client_id", sa.String(length=32), nullable=False),
        sa.Column("queue_item_id", sa.String(length=32), nullable=False),
        sa.Column(
            "claimed_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.func.replace(
                sa.cast(sa.func.gen_random_uuid(), sa.String()),
                "-",
                "",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_client_id"], ["agent_access__agent_client_model.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["queue_item_id"], ["competency_matrix__queued_question_model.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_client_id", name="matrix_question_claim_client_uniq"),
        sa.UniqueConstraint("queue_item_id", name="matrix_question_claim_queue_item_uniq"),
    )
    op.create_index(
        "matrix_question_claim_expiry_idx",
        "agent_access__matrix_question_claim_model",
        ["expires_at", "id"],
        unique=False,
    )
    op.create_table(
        "agent_access__matrix_question_draft_completion_model",
        sa.Column("claim_id", sa.String(length=32), nullable=False),
        sa.Column("agent_client_id", sa.String(length=32), nullable=False),
        sa.Column("queue_item_id", sa.String(length=32), nullable=False),
        sa.Column("matrix_item_id", sa.String(length=32), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "completed_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_client_id"], ["agent_access__agent_client_model.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("claim_id"),
    )
    op.create_index(
        "matrix_question_draft_completion_client_completed_idx",
        "agent_access__matrix_question_draft_completion_model",
        ["agent_client_id", "completed_at", "claim_id"],
        unique=False,
    )
    op.create_table(
        "agent_access__agent_audit_event_model",
        sa.Column("agent_client_id", sa.String(length=32), nullable=False),
        sa.Column("certificate_id", sa.String(length=32), nullable=False),
        sa.Column(
            "action",
            enum_types["agent_action"],
            nullable=False,
        ),
        sa.Column("queue_item_id", sa.String(length=32), nullable=True),
        sa.Column("matrix_item_id", sa.String(length=32), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=False),
        sa.Column(
            "result",
            enum_types["agent_audit_result"],
            nullable=False,
        ),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.func.replace(
                sa.cast(sa.func.gen_random_uuid(), sa.String()),
                "-",
                "",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_client_id"], ["agent_access__agent_client_model.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["certificate_id"], ["agent_access__agent_certificate_model.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "agent_audit_action_result_created_idx",
        "agent_access__agent_audit_event_model",
        ["action", "result", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "agent_audit_client_created_idx",
        "agent_access__agent_audit_event_model",
        ["agent_client_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "agent_audit_created_idx",
        "agent_access__agent_audit_event_model",
        ["created_at", "id"],
        unique=False,
    )
    op.create_table(
        "agent_access__agent_certificate_rotation_model",
        sa.Column("rotation_id", sa.String(length=255), nullable=False),
        sa.Column("agent_client_id", sa.String(length=32), nullable=False),
        sa.Column("current_certificate_id", sa.String(length=32), nullable=False),
        sa.Column("replacement_certificate_id", sa.String(length=32), nullable=False),
        sa.Column("csr_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "normal_access_until",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "confirmed_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            sa.column("current_certificate_id") != sa.column("replacement_certificate_id"),
            name="agent_certificate_rotation_distinct_certificates_check",
        ),
        sa.ForeignKeyConstraint(
            ["agent_client_id"], ["agent_access__agent_client_model.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["current_certificate_id"],
            ["agent_access__agent_certificate_model.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_certificate_id"],
            ["agent_access__agent_certificate_model.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("rotation_id"),
        sa.UniqueConstraint(
            "replacement_certificate_id", name="agent_certificate_rotation_replacement_uniq"
        ),
    )
    op.create_index(
        "agent_certificate_rotation_client_created_idx",
        "agent_access__agent_certificate_rotation_model",
        ["agent_client_id", "created_at", "rotation_id"],
        unique=False,
    )
    op.create_index(
        "agent_certificate_rotation_pending_current_uniq",
        "agent_access__agent_certificate_rotation_model",
        ["current_certificate_id"],
        unique=True,
        postgresql_where=sa.column("confirmed_at").is_(None),
    )


def downgrade() -> None:
    op.drop_index(
        "agent_certificate_rotation_pending_current_uniq",
        table_name="agent_access__agent_certificate_rotation_model",
    )
    op.drop_index(
        "agent_certificate_rotation_client_created_idx",
        table_name="agent_access__agent_certificate_rotation_model",
    )
    op.drop_table("agent_access__agent_certificate_rotation_model")
    op.drop_index("agent_audit_created_idx", table_name="agent_access__agent_audit_event_model")
    op.drop_index(
        "agent_audit_client_created_idx", table_name="agent_access__agent_audit_event_model"
    )
    op.drop_index(
        "agent_audit_action_result_created_idx", table_name="agent_access__agent_audit_event_model"
    )
    op.drop_table("agent_access__agent_audit_event_model")
    op.drop_index(
        "matrix_question_draft_completion_client_completed_idx",
        table_name="agent_access__matrix_question_draft_completion_model",
    )
    op.drop_table("agent_access__matrix_question_draft_completion_model")
    op.drop_index(
        "matrix_question_claim_expiry_idx", table_name="agent_access__matrix_question_claim_model"
    )
    op.drop_table("agent_access__matrix_question_claim_model")
    op.drop_index(
        "agent_certificate_revoked_expiry_idx", table_name="agent_access__agent_certificate_model"
    )
    op.drop_index(
        "agent_certificate_client_expiry_idx", table_name="agent_access__agent_certificate_model"
    )
    op.drop_table("agent_access__agent_certificate_model")
    op.drop_index("agent_client_status_created_idx", table_name="agent_access__agent_client_model")
    op.drop_index("agent_client_name_lower_uniq", table_name="agent_access__agent_client_model")
    op.drop_table("agent_access__agent_client_model")
    for enum_type in reversed(tuple(_enum_types_by_name().values())):
        enum_type.drop(op.get_bind(), checkfirst=False)
