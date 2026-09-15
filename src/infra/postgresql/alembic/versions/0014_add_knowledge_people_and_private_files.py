from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlalchemy_dev_utils.types.datetime


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge__knowledge_item_model",
        sa.Column("kind", sa.Enum("PERSON", name="knowledge_item_kind_enum"), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
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
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("description")) <= 100000,
            name="knowledge_items_description_length_check",
        ),
        sa.ForeignKeyConstraint(
            ["author_username"], ["auth__user_model.username"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "author_username", name="knowledge_items_id_author_uniq"),
    )
    op.create_index(
        "knowledge_items_author_kind_name_id_idx",
        "knowledge__knowledge_item_model",
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
        "knowledge__knowledge_item_model",
        [
            "author_username",
            "kind",
            sa.column("updated_at").desc(),
            sa.column("id").desc(),
        ],
        unique=False,
    )
    op.create_table(
        "knowledge__knowledge_tag_model",
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_username"], ["auth__user_model.username"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "author_username", name="knowledge_tags_id_author_uniq"),
    )
    op.create_index(
        "knowledge_tags_author_name_id_idx",
        "knowledge__knowledge_tag_model",
        ["author_username", sa.func.lower(sa.column("name")).label("name_lower"), "id"],
        unique=False,
    )
    op.create_index(
        "knowledge_tags_author_name_lower_uniq",
        "knowledge__knowledge_tag_model",
        ["author_username", sa.func.lower(sa.column("name")).label("name_lower")],
        unique=True,
    )
    op.create_index(
        "knowledge_tags_name_trgm_idx",
        "knowledge__knowledge_tag_model",
        [sa.func.lower(sa.column("name")).label("name_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_lower_trgm": "gin_trgm_ops"},
    )
    op.create_table(
        "knowledge__person_relationship_type_model",
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("is_symmetric", sa.Boolean(), nullable=False),
        sa.Column("forward_name", sa.String(length=255), nullable=False),
        sa.Column("reverse_name", sa.String(length=255), nullable=False),
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
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.CheckConstraint(
            sa.or_(
                sa.and_(
                    sa.column("is_symmetric").is_(True),
                    sa.func.char_length(sa.func.trim(sa.column("forward_name"))) > 0,
                    sa.column("reverse_name") == sa.column("forward_name"),
                ),
                sa.and_(
                    sa.column("is_symmetric").is_(False),
                    sa.func.char_length(sa.func.trim(sa.column("forward_name"))) > 0,
                    sa.func.char_length(sa.func.trim(sa.column("reverse_name"))) > 0,
                ),
            ),
            name="person_relationship_types_names_check",
        ),
        sa.ForeignKeyConstraint(
            ["author_username"], ["auth__user_model.username"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "author_username", name="person_relationship_types_id_author_uniq"
        ),
    )
    op.create_index(
        "person_relationship_types_author_name_id_idx",
        "knowledge__person_relationship_type_model",
        [
            "author_username",
            sa.func.lower(sa.column("forward_name")).label("forward_name_lower"),
            "id",
        ],
        unique=False,
    )
    op.create_table(
        "knowledge__knowledge_file_model",
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("ATTACHMENT", "PERSON_PHOTO", name="knowledge_file_kind_enum"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
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
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("original_sha256")) == 64,
            name="knowledge_files_sha256_length_check",
        ),
        sa.CheckConstraint(
            sa.and_(
                sa.func.char_length(sa.func.trim(sa.column("name"))) > 0,
                sa.func.char_length(sa.func.trim(sa.column("original_name"))) > 0,
            ),
            name="knowledge_files_names_check",
        ),
        sa.CheckConstraint(
            sa.column("size_bytes") >= 0,
            name="knowledge_files_non_negative_size_check",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "author_username"],
            [
                "knowledge__knowledge_item_model.id",
                "knowledge__knowledge_item_model.author_username",
            ],
            name="knowledge_files_item_author_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "author_username", name="knowledge_files_id_author_uniq"),
        sa.UniqueConstraint("relative_path"),
    )
    op.create_index(
        "knowledge_files_author_item_kind_id_idx",
        "knowledge__knowledge_file_model",
        ["author_username", "item_id", "kind", "id"],
        unique=False,
    )
    op.create_index(
        "knowledge_files_one_person_photo_idx",
        "knowledge__knowledge_file_model",
        ["item_id"],
        unique=True,
        postgresql_where=sa.column("kind") == sa.literal("PERSON_PHOTO"),
    )
    op.create_table(
        "knowledge__knowledge_item_tag_model",
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("tag_id", sa.String(length=32), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "author_username"],
            [
                "knowledge__knowledge_item_model.id",
                "knowledge__knowledge_item_model.author_username",
            ],
            name="knowledge_item_tags_item_author_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id", "author_username"],
            ["knowledge__knowledge_tag_model.id", "knowledge__knowledge_tag_model.author_username"],
            name="knowledge_item_tags_tag_author_fk",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("item_id", "tag_id"),
    )
    op.create_index(
        "knowledge_item_tags_author_tag_item_idx",
        "knowledge__knowledge_item_tag_model",
        ["author_username", "tag_id", "item_id"],
        unique=False,
    )
    op.create_table(
        "knowledge__person_details_model",
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("middle_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("telegram", sa.String(length=255), nullable=False),
        sa.Column("birthday_day", sa.Integer(), nullable=True),
        sa.Column("birthday_month", sa.Integer(), nullable=True),
        sa.Column("birthday_year", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            sa.or_(
                sa.and_(
                    sa.column("birthday_day").is_(None),
                    sa.column("birthday_month").is_(None),
                    sa.column("birthday_year").is_(None),
                ),
                sa.and_(
                    sa.column("birthday_day").is_not(None),
                    sa.column("birthday_month").is_not(None),
                    sa.column("birthday_day").between(1, 31),
                    sa.column("birthday_month").between(1, 12),
                    sa.or_(
                        sa.column("birthday_year").is_(None),
                        sa.column("birthday_year").between(1, 9999),
                    ),
                    sa.column("birthday_day")
                    <= sa.case(
                        (
                            sa.column("birthday_month").in_((1, 3, 5, 7, 8, 10, 12)),
                            31,
                        ),
                        (sa.column("birthday_month").in_((4, 6, 9, 11)), 30),
                        (sa.column("birthday_year").is_(None), 29),
                        (
                            sa.or_(
                                sa.column("birthday_year") % 400 == 0,
                                sa.and_(
                                    sa.column("birthday_year") % 4 == 0,
                                    sa.column("birthday_year") % 100 != 0,
                                ),
                            ),
                            29,
                        ),
                        else_=28,
                    ),
                    sa.or_(
                        sa.column("birthday_year").is_(None),
                        sa.func.make_date(
                            sa.column("birthday_year"),
                            sa.column("birthday_month"),
                            sa.column("birthday_day"),
                        )
                        <= sa.func.current_date(),
                    ),
                ),
            ),
            name="person_details_birthday_check",
        ),
        sa.CheckConstraint(
            sa.and_(
                sa.func.char_length(sa.func.trim(sa.column("last_name"))) > 0,
                sa.func.char_length(sa.func.trim(sa.column("first_name"))) > 0,
            ),
            name="person_details_required_names_check",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "author_username"],
            [
                "knowledge__knowledge_item_model.id",
                "knowledge__knowledge_item_model.author_username",
            ],
            name="person_details_item_author_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.UniqueConstraint("item_id", "author_username", name="person_details_id_author_uniq"),
    )
    op.create_index(
        "person_details_author_email_item_idx",
        "knowledge__person_details_model",
        [
            "author_username",
            sa.func.lower(sa.column("email")).label("email_lower"),
            "item_id",
        ],
        unique=False,
    )
    op.create_index(
        "person_details_author_name_search_idx",
        "knowledge__person_details_model",
        [
            "author_username",
            sa.func.lower(sa.column("last_name")).label("last_name_lower"),
            sa.func.lower(sa.column("first_name")).label("first_name_lower"),
            "item_id",
        ],
        unique=False,
    )
    op.create_index(
        "person_details_email_trgm_idx",
        "knowledge__person_details_model",
        [sa.func.lower(sa.column("email")).label("email_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"email_lower_trgm": "gin_trgm_ops"},
    )
    op.create_index(
        "person_details_first_name_trgm_idx",
        "knowledge__person_details_model",
        [sa.func.lower(sa.column("first_name")).label("first_name_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"first_name_lower_trgm": "gin_trgm_ops"},
    )
    op.create_index(
        "person_details_last_name_trgm_idx",
        "knowledge__person_details_model",
        [sa.func.lower(sa.column("last_name")).label("last_name_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"last_name_lower_trgm": "gin_trgm_ops"},
    )
    op.create_index(
        "person_details_middle_name_trgm_idx",
        "knowledge__person_details_model",
        [sa.func.lower(sa.column("middle_name")).label("middle_name_lower_trgm")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"middle_name_lower_trgm": "gin_trgm_ops"},
    )
    op.create_table(
        "knowledge__person_relationship_model",
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("source_person_id", sa.String(length=32), nullable=False),
        sa.Column("target_person_id", sa.String(length=32), nullable=False),
        sa.Column("relationship_type_id", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
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
        sa.Column(
            "created_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sqlalchemy_dev_utils.types.datetime.UTCDateTime(timezone=True),
            server_default=sa.func.timezone("utc", sa.func.current_timestamp()),
            nullable=False,
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("note")) <= 10000,
            name="person_relationships_note_length_check",
        ),
        sa.CheckConstraint(
            sa.column("source_person_id") != sa.column("target_person_id"),
            name="person_relationships_not_self_check",
        ),
        sa.ForeignKeyConstraint(
            ["relationship_type_id", "author_username"],
            [
                "knowledge__person_relationship_type_model.id",
                "knowledge__person_relationship_type_model.author_username",
            ],
            name="person_relationships_type_author_fk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_person_id", "author_username"],
            [
                "knowledge__person_details_model.item_id",
                "knowledge__person_details_model.author_username",
            ],
            name="person_relationships_source_author_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_person_id", "author_username"],
            [
                "knowledge__person_details_model.item_id",
                "knowledge__person_details_model.author_username",
            ],
            name="person_relationships_target_author_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "person_relationships_author_pair_type_uniq",
        "knowledge__person_relationship_model",
        [
            "author_username",
            sa.func.least(
                sa.column("source_person_id"),
                sa.column("target_person_id"),
            ),
            sa.func.greatest(
                sa.column("source_person_id"),
                sa.column("target_person_id"),
            ),
            "relationship_type_id",
        ],
        unique=True,
    )
    op.create_index(
        "person_relationships_author_source_idx",
        "knowledge__person_relationship_model",
        ["author_username", "source_person_id", "id"],
        unique=False,
    )
    op.create_index(
        "person_relationships_author_target_idx",
        "knowledge__person_relationship_model",
        ["author_username", "target_person_id", "id"],
        unique=False,
    )
    op.create_index(
        "person_relationships_author_type_id_idx",
        "knowledge__person_relationship_model",
        ["author_username", "relationship_type_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "person_relationships_author_type_id_idx",
        table_name="knowledge__person_relationship_model",
    )
    op.drop_index(
        "person_relationships_author_target_idx", table_name="knowledge__person_relationship_model"
    )
    op.drop_index(
        "person_relationships_author_source_idx", table_name="knowledge__person_relationship_model"
    )
    op.drop_index(
        "person_relationships_author_pair_type_uniq",
        table_name="knowledge__person_relationship_model",
    )
    op.drop_table("knowledge__person_relationship_model")
    op.drop_index(
        "person_details_middle_name_trgm_idx",
        table_name="knowledge__person_details_model",
    )
    op.drop_index(
        "person_details_last_name_trgm_idx",
        table_name="knowledge__person_details_model",
    )
    op.drop_index(
        "person_details_first_name_trgm_idx",
        table_name="knowledge__person_details_model",
    )
    op.drop_index(
        "person_details_email_trgm_idx",
        table_name="knowledge__person_details_model",
    )
    op.drop_index(
        "person_details_author_name_search_idx", table_name="knowledge__person_details_model"
    )
    op.drop_index(
        "person_details_author_email_item_idx", table_name="knowledge__person_details_model"
    )
    op.drop_table("knowledge__person_details_model")
    op.drop_index(
        "knowledge_item_tags_author_tag_item_idx", table_name="knowledge__knowledge_item_tag_model"
    )
    op.drop_table("knowledge__knowledge_item_tag_model")
    op.drop_index(
        "knowledge_files_one_person_photo_idx",
        table_name="knowledge__knowledge_file_model",
    )
    op.drop_index(
        "knowledge_files_author_item_kind_id_idx", table_name="knowledge__knowledge_file_model"
    )
    op.drop_table("knowledge__knowledge_file_model")
    op.drop_index(
        "person_relationship_types_author_name_id_idx",
        table_name="knowledge__person_relationship_type_model",
    )
    op.drop_table("knowledge__person_relationship_type_model")
    op.drop_index(
        "knowledge_tags_name_trgm_idx",
        table_name="knowledge__knowledge_tag_model",
    )
    op.drop_index(
        "knowledge_tags_author_name_lower_uniq", table_name="knowledge__knowledge_tag_model"
    )
    op.drop_index("knowledge_tags_author_name_id_idx", table_name="knowledge__knowledge_tag_model")
    op.drop_table("knowledge__knowledge_tag_model")
    op.drop_index(
        "knowledge_items_author_kind_updated_id_idx", table_name="knowledge__knowledge_item_model"
    )
    op.drop_index(
        "knowledge_items_author_kind_name_id_idx", table_name="knowledge__knowledge_item_model"
    )
    op.drop_table("knowledge__knowledge_item_model")
    postgresql.ENUM(
        "ATTACHMENT",
        "PERSON_PHOTO",
        name="knowledge_file_kind_enum",
    ).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM(
        "PERSON",
        name="knowledge_item_kind_enum",
    ).drop(op.get_bind(), checkfirst=False)
