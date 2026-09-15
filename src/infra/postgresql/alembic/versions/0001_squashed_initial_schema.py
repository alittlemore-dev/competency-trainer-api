import os

from alembic import op
from argon2 import PasswordHasher
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _enum_types_by_name() -> dict[str, postgresql.ENUM]:
    return {
        "article_reaction_kind": postgresql.ENUM(
            "HEART",
            "FIRE",
            "THINKING",
            "NEUTRAL",
            "POOP",
            name="article_reaction_kind_enum",
            create_type=False,
        ),
        "article_view_source_category": postgresql.ENUM(
            "DIRECT",
            "INTERNAL",
            "SEARCH",
            "SOCIAL",
            "EXTERNAL",
            "UNKNOWN",
            name="article_view_source_category_enum",
            create_type=False,
        ),
        "grade": postgresql.ENUM(
            "JUNIOR",
            "JUNIOR_PLUS",
            "MIDDLE",
            "MIDDLE_PLUS",
            "SENIOR",
            name="grade_enum",
            create_type=False,
        ),
        "interview_frequency": postgresql.ENUM(
            "CONSTANTLY",
            "OFTEN",
            "RARELY",
            "NEVER_SEEN",
            name="interview_frequency_enum",
            create_type=False,
        ),
        "language": postgresql.ENUM("RU", "EN", name="language_enum", create_type=False),
        "publish_status": postgresql.ENUM(
            "DRAFT",
            "PUBLISHED",
            name="publish_status_enum",
            create_type=False,
        ),
        "role": postgresql.ENUM(
            "ANON",
            "USER",
            "MODERATOR",
            "ADMIN",
            "OWNER",
            name="role_enum",
            create_type=False,
        ),
    }


def _create_initial_owner(role_type: postgresql.ENUM) -> None:
    owner_table = sa.table(
        "auth__user_model",
        sa.column("username", sa.String(255)),
        sa.column("password_hash", sa.String(127)),
        sa.column("role", role_type),
        sa.column("is_active", sa.Boolean()),
    )
    statement = (
        postgresql.insert(owner_table)
        .values(
            username=os.environ["OWNER_INIT_LOGIN"],
            password_hash=PasswordHasher().hash(os.environ["OWNER_INIT_PASSWORD"]),
            role="OWNER",
            is_active=True,
        )
        .on_conflict_do_nothing(index_elements=["username"])
    )
    op.get_bind().execute(statement)


def upgrade() -> None:
    enum_types = _enum_types_by_name()
    for enum_type in enum_types.values():
        enum_type.create(op.get_bind(), checkfirst=True)

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "articles__article_model",
        sa.Column("title_ru", sa.String(length=255), nullable=False),
        sa.Column("title_en", sa.String(length=255), nullable=False),
        sa.Column("content_ru", sa.String(), nullable=False),
        sa.Column("content_en", sa.String(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("folder_ru", sa.String(length=255), nullable=False),
        sa.Column("folder_en", sa.String(length=255), nullable=False),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("seo_title_ru", sa.String(length=255), nullable=True),
        sa.Column("seo_title_en", sa.String(length=255), nullable=True),
        sa.Column("seo_description_ru", sa.String(length=320), nullable=True),
        sa.Column("seo_description_en", sa.String(length=320), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_image_alt_ru", sa.String(length=255), nullable=True),
        sa.Column("cover_image_alt_en", sa.String(length=255), nullable=True),
        sa.Column(
            "search_vector_ru",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(title_ru, '')), 'A') || setweight(to_tsvector('simple', coalesce(content_ru, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "search_vector_en",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(title_en, '')), 'A') || setweight(to_tsvector('simple', coalesce(content_en, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "publish_status",
            enum_types["publish_status"],
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "articles_article_publish_status_published_at_idx",
        "articles__article_model",
        ["publish_status", "published_at"],
        unique=False,
    )
    op.create_index(
        "articles_article_publish_status_published_updated_idx",
        "articles__article_model",
        [
            "publish_status",
            sa.literal_column("published_at DESC NULLS LAST"),
            sa.literal_column("updated_at DESC"),
        ],
        unique=False,
    )
    op.create_index(
        "articles_article_search_vector_en_gin_idx",
        "articles__article_model",
        ["search_vector_en"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "articles_article_search_vector_gin_idx",
        "articles__article_model",
        ["search_vector_ru"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "articles_article_tree_en_published_idx",
        "articles__article_model",
        [
            "folder_en",
            sa.literal_column("published_at DESC NULLS LAST"),
            sa.literal_column("updated_at DESC"),
            "title_en",
        ],
        unique=False,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=sa.text("publish_status = 'PUBLISHED'"),
    )
    op.create_index(
        "articles_article_tree_ru_published_idx",
        "articles__article_model",
        [
            "folder_ru",
            sa.literal_column("published_at DESC NULLS LAST"),
            sa.literal_column("updated_at DESC"),
            "title_ru",
        ],
        unique=False,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=sa.text("publish_status = 'PUBLISHED'"),
    )
    op.create_index(
        op.f("ix_articles__article_model_slug"), "articles__article_model", ["slug"], unique=True
    )
    op.create_table(
        "articles__tag_model",
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column(
            "deleted_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "articles_tag_name_en_trgm_idx",
        "articles__tag_model",
        [sa.literal_column("lower(name_en)").label("name_en_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_en_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "articles_tag_name_ru_trgm_idx",
        "articles__tag_model",
        [sa.literal_column("lower(name_ru)").label("name_ru_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "articles_tag_slug_trgm_idx",
        "articles__tag_model",
        [sa.literal_column("lower(slug)").label("slug_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"slug_lower": "gin_trgm_ops"},
    )
    op.create_index(
        op.f("ix_articles__tag_model_slug"), "articles__tag_model", ["slug"], unique=True
    )
    op.create_table(
        "auth__user_model",
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=127), nullable=False),
        sa.Column(
            "role",
            enum_types["role"],
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("username"),
    )
    op.create_index(
        "users_managed_accounts_list_idx",
        "auth__user_model",
        ["role", sa.literal_column("lower(username)").label("username_lower"), "username"],
        unique=False,
    )
    op.create_index(
        "users_single_owner_uniq",
        "auth__user_model",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'OWNER'"),
    )
    op.create_index("users_username_idx", "auth__user_model", ["username"], unique=False)
    op.create_index(
        "users_username_lower_uniq",
        "auth__user_model",
        [sa.literal_column("lower(username)").label("username_lower")],
        unique=True,
    )
    _create_initial_owner(enum_types["role"])
    op.create_table(
        "competency_matrix__competency_matrix_sheet_model",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        "cm_sheet_key_lower_idx",
        "competency_matrix__competency_matrix_sheet_model",
        [sa.literal_column("lower(key)").label("sheet_key_lower")],
        unique=False,
    )
    op.create_index(
        "cm_sheet_priority_idx",
        "competency_matrix__competency_matrix_sheet_model",
        ["priority", "id"],
        unique=False,
    )
    op.create_table(
        "competency_matrix__external_resource_model",
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "cm_external_resource_name_en_trgm_idx",
        "competency_matrix__external_resource_model",
        [sa.literal_column("lower(name_en)").label("name_en_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_en_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "cm_external_resource_name_ru_trgm_idx",
        "competency_matrix__external_resource_model",
        [sa.literal_column("lower(name_ru)").label("name_ru_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "cm_external_resource_url_trgm_idx",
        "competency_matrix__external_resource_model",
        [sa.literal_column("lower(url)").label("url_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"url_lower": "gin_trgm_ops"},
    )
    op.create_table(
        "contacts__contact_me_model",
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telegram", sa.String(length=256), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "resumes__resume_model",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "language",
            enum_types["language"],
            nullable=False,
        ),
        sa.Column("author_username", sa.String(length=255), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "resumes_resume_author_updated_id_idx",
        "resumes__resume_model",
        ["author_username", sa.literal_column("updated_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_table(
        "articles__article_daily_analytics_model",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "source_category",
            enum_types["article_view_source_category"],
            nullable=False,
        ),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("engaged_view_count", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles__article_model.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "date",
            "source_category",
            name="articles_daily_analytics_article_date_source_uniq",
        ),
    )
    op.create_table(
        "articles__article_reaction_model",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("article_scoped_voter_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "reaction_kind",
            enum_types["article_reaction_kind"],
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            UTCDateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles__article_model.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "article_scoped_voter_hash", name="articles_reaction_article_voter_uniq"
        ),
    )
    op.create_table(
        "articles__article_to_tag_secondary_model",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles__article_model.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["articles__tag_model.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "tag_id", name="articles_article_tag_uniq"),
    )
    op.create_table(
        "competency_matrix__competency_matrix_section_model",
        sa.Column("sheet_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sheet_id"],
            ["competency_matrix__competency_matrix_sheet_model.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sheet_id", "name_en", name="cm_section_sheet_name_en_uniq"),
        sa.UniqueConstraint("sheet_id", "name_ru", name="cm_section_sheet_name_ru_uniq"),
    )
    op.create_index(
        "cm_section_sheet_en_idx",
        "competency_matrix__competency_matrix_section_model",
        ["sheet_id", "name_en", "id"],
        unique=False,
    )
    op.create_index(
        "cm_section_sheet_ru_idx",
        "competency_matrix__competency_matrix_section_model",
        ["sheet_id", "name_ru", "id"],
        unique=False,
    )
    op.create_index(
        "cm_section_sheet_priority_idx",
        "competency_matrix__competency_matrix_section_model",
        ["sheet_id", "priority", "id"],
        unique=False,
    )
    op.create_table(
        "competency_matrix__queued_question_model",
        sa.Column("question", sa.String(length=255), nullable=False),
        sa.Column(
            "grade",
            enum_types["grade"],
            nullable=True,
        ),
        sa.Column("sheet", sa.String(length=255), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("subsection", sa.String(length=255), nullable=True),
        sa.Column("suggested_by_username", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            UTCDateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["suggested_by_username"], ["auth__user_model.username"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "cm_queued_question_fifo_idx",
        "competency_matrix__queued_question_model",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "cm_queued_question_suggested_by_idx",
        "competency_matrix__queued_question_model",
        ["suggested_by_username"],
        unique=False,
    )
    op.create_table(
        "competency_matrix__competency_matrix_subsection_model",
        sa.Column(
            "section_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["competency_matrix__competency_matrix_section_model.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "name_en", name="cm_subsection_section_name_en_uniq"),
        sa.UniqueConstraint("section_id", "name_ru", name="cm_subsection_section_name_ru_uniq"),
    )
    op.create_index(
        "cm_subsection_section_en_idx",
        "competency_matrix__competency_matrix_subsection_model",
        ["section_id", "name_en", "id"],
        unique=False,
    )
    op.create_index(
        "cm_subsection_section_ru_idx",
        "competency_matrix__competency_matrix_subsection_model",
        ["section_id", "name_ru", "id"],
        unique=False,
    )
    op.create_index(
        "cm_subsection_section_priority_idx",
        "competency_matrix__competency_matrix_subsection_model",
        ["section_id", "priority", "id"],
        unique=False,
    )
    op.create_table(
        "competency_matrix__competency_matrix_item_model",
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("question_ru", sa.String(length=255), nullable=False),
        sa.Column("question_en", sa.String(length=255), nullable=False),
        sa.Column("answer_ru", sa.String(), nullable=False),
        sa.Column("answer_en", sa.String(), nullable=False),
        sa.Column("interview_expected_answer_ru", sa.String(), nullable=False),
        sa.Column("interview_expected_answer_en", sa.String(), nullable=False),
        sa.Column(
            "subsection_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "grade",
            enum_types["grade"],
            nullable=True,
        ),
        sa.Column(
            "interview_frequency",
            enum_types["interview_frequency"],
            nullable=True,
        ),
        sa.Column(
            "published_at",
            UTCDateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "publish_status",
            enum_types["publish_status"],
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subsection_id"],
            ["competency_matrix__competency_matrix_subsection_model.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "cmi_subsection_status_grade_idx",
        "competency_matrix__competency_matrix_item_model",
        ["subsection_id", "publish_status", "grade", "id"],
        unique=False,
    )
    op.create_index(
        "cmi_workspace_missing_fields_idx",
        "competency_matrix__competency_matrix_item_model",
        [
            sa.literal_column(
                "(length(TRIM(BOTH FROM slug)) = 0 OR "
                "grade IS NULL OR "
                "length(TRIM(BOTH FROM question_ru)) = 0 OR "
                "length(TRIM(BOTH FROM question_en)) = 0 OR "
                "length(TRIM(BOTH FROM answer_ru)) = 0 OR "
                "length(TRIM(BOTH FROM answer_en)) = 0 OR "
                "length(TRIM(BOTH FROM interview_expected_answer_ru)) = 0 OR "
                "length(TRIM(BOTH FROM interview_expected_answer_en)) = 0)"
            )
        ],
        unique=False,
    )
    op.create_index(
        "cmi_workspace_question_en_trgm_idx",
        "competency_matrix__competency_matrix_item_model",
        [sa.literal_column("lower(question_en)").label("workspace_question_en_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"workspace_question_en_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "cmi_workspace_question_ru_trgm_idx",
        "competency_matrix__competency_matrix_item_model",
        [sa.literal_column("lower(question_ru)").label("workspace_question_ru_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"workspace_question_ru_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "cmi_workspace_slug_trgm_idx",
        "competency_matrix__competency_matrix_item_model",
        [sa.literal_column("lower(slug)").label("workspace_slug_lower")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"workspace_slug_lower": "gin_trgm_ops"},
    )
    op.create_index(
        "cmi_workspace_status_published_at_idx",
        "competency_matrix__competency_matrix_item_model",
        ["publish_status", sa.literal_column("published_at DESC NULLS LAST"), "id"],
        unique=False,
    )
    op.create_index(
        "cmi_workspace_subsection_status_grade_idx",
        "competency_matrix__competency_matrix_item_model",
        ["subsection_id", "publish_status", "grade", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competency_matrix__competency_matrix_item_model_slug"),
        "competency_matrix__competency_matrix_item_model",
        ["slug"],
        unique=True,
    )
    op.create_table(
        "competency_matrix__resource_to_item_secondary_model",
        sa.Column("item_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "resource_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("context_ru", sa.String(), nullable=False),
        sa.Column("context_en", sa.String(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["competency_matrix__competency_matrix_item_model.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["competency_matrix__external_resource_model.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "resource_id", name="cm_resource_item_uniq"),
    )


def downgrade() -> None:
    enum_types = _enum_types_by_name()

    op.drop_table("competency_matrix__resource_to_item_secondary_model")
    op.drop_index(
        op.f("ix_competency_matrix__competency_matrix_item_model_slug"),
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_index(
        "cmi_workspace_subsection_status_grade_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_index(
        "cmi_workspace_status_published_at_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_index(
        "cmi_workspace_slug_trgm_idx",
        table_name="competency_matrix__competency_matrix_item_model",
        postgresql_using="gin",
        postgresql_ops={"workspace_slug_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "cmi_workspace_question_ru_trgm_idx",
        table_name="competency_matrix__competency_matrix_item_model",
        postgresql_using="gin",
        postgresql_ops={"workspace_question_ru_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "cmi_workspace_question_en_trgm_idx",
        table_name="competency_matrix__competency_matrix_item_model",
        postgresql_using="gin",
        postgresql_ops={"workspace_question_en_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "cmi_workspace_missing_fields_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_index(
        "cmi_subsection_status_grade_idx",
        table_name="competency_matrix__competency_matrix_item_model",
    )
    op.drop_table("competency_matrix__competency_matrix_item_model")
    op.drop_index(
        "cm_subsection_section_priority_idx",
        table_name="competency_matrix__competency_matrix_subsection_model",
    )
    op.drop_index(
        "cm_subsection_section_ru_idx",
        table_name="competency_matrix__competency_matrix_subsection_model",
    )
    op.drop_index(
        "cm_subsection_section_en_idx",
        table_name="competency_matrix__competency_matrix_subsection_model",
    )
    op.drop_table("competency_matrix__competency_matrix_subsection_model")
    op.drop_index(
        "cm_queued_question_suggested_by_idx", table_name="competency_matrix__queued_question_model"
    )
    op.drop_index(
        "cm_queued_question_fifo_idx", table_name="competency_matrix__queued_question_model"
    )
    op.drop_table("competency_matrix__queued_question_model")
    op.drop_index(
        "cm_section_sheet_priority_idx",
        table_name="competency_matrix__competency_matrix_section_model",
    )
    op.drop_index(
        "cm_section_sheet_ru_idx", table_name="competency_matrix__competency_matrix_section_model"
    )
    op.drop_index(
        "cm_section_sheet_en_idx", table_name="competency_matrix__competency_matrix_section_model"
    )
    op.drop_table("competency_matrix__competency_matrix_section_model")
    op.drop_table("articles__article_to_tag_secondary_model")
    op.drop_table("articles__article_reaction_model")
    op.drop_table("articles__article_daily_analytics_model")
    op.drop_index("resumes_resume_author_updated_id_idx", table_name="resumes__resume_model")
    op.drop_table("resumes__resume_model")
    op.drop_table("contacts__contact_me_model")
    op.drop_index(
        "cm_external_resource_url_trgm_idx",
        table_name="competency_matrix__external_resource_model",
        postgresql_using="gin",
        postgresql_ops={"url_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "cm_external_resource_name_ru_trgm_idx",
        table_name="competency_matrix__external_resource_model",
        postgresql_using="gin",
        postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "cm_external_resource_name_en_trgm_idx",
        table_name="competency_matrix__external_resource_model",
        postgresql_using="gin",
        postgresql_ops={"name_en_lower": "gin_trgm_ops"},
    )
    op.drop_table("competency_matrix__external_resource_model")
    op.drop_index(
        "cm_sheet_priority_idx", table_name="competency_matrix__competency_matrix_sheet_model"
    )
    op.drop_index(
        "cm_sheet_key_lower_idx", table_name="competency_matrix__competency_matrix_sheet_model"
    )
    op.drop_table("competency_matrix__competency_matrix_sheet_model")
    op.drop_index("users_username_lower_uniq", table_name="auth__user_model")
    op.drop_index("users_username_idx", table_name="auth__user_model")
    op.drop_index(
        "users_single_owner_uniq",
        table_name="auth__user_model",
        postgresql_where=sa.text("role = 'OWNER'"),
    )
    op.drop_index("users_managed_accounts_list_idx", table_name="auth__user_model")
    op.drop_table("auth__user_model")
    op.drop_index(op.f("ix_articles__tag_model_slug"), table_name="articles__tag_model")
    op.drop_index(
        "articles_tag_slug_trgm_idx",
        table_name="articles__tag_model",
        postgresql_using="gin",
        postgresql_ops={"slug_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "articles_tag_name_ru_trgm_idx",
        table_name="articles__tag_model",
        postgresql_using="gin",
        postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
    )
    op.drop_index(
        "articles_tag_name_en_trgm_idx",
        table_name="articles__tag_model",
        postgresql_using="gin",
        postgresql_ops={"name_en_lower": "gin_trgm_ops"},
    )
    op.drop_table("articles__tag_model")
    op.drop_index(op.f("ix_articles__article_model_slug"), table_name="articles__article_model")
    op.drop_index(
        "articles_article_tree_ru_published_idx",
        table_name="articles__article_model",
        postgresql_include=("slug", "publish_status"),
        postgresql_where=sa.text("publish_status = 'PUBLISHED'"),
    )
    op.drop_index(
        "articles_article_tree_en_published_idx",
        table_name="articles__article_model",
        postgresql_include=("slug", "publish_status"),
        postgresql_where=sa.text("publish_status = 'PUBLISHED'"),
    )
    op.drop_index(
        "articles_article_search_vector_gin_idx",
        table_name="articles__article_model",
        postgresql_using="gin",
    )
    op.drop_index(
        "articles_article_search_vector_en_gin_idx",
        table_name="articles__article_model",
        postgresql_using="gin",
    )
    op.drop_index(
        "articles_article_publish_status_published_updated_idx",
        table_name="articles__article_model",
    )
    op.drop_index(
        "articles_article_publish_status_published_at_idx", table_name="articles__article_model"
    )
    op.drop_table("articles__article_model")

    for enum_type in reversed(tuple(enum_types.values())):
        enum_type.drop(op.get_bind(), checkfirst=True)
