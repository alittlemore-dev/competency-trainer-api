from sqlalchemy import text

from tests.test_cases import StorageTestCase


class TestNativeEnumColumns(StorageTestCase):
    async def test_enum_columns_use_postgresql_enum_types(self) -> None:
        expected = {
            ("articles__article_daily_analytics_model", "source_category"): (
                "article_view_source_category_enum",
                "e",
            ),
            ("articles__article_file_usage_model", "usage"): ("file_purpose_enum", "e"),
            ("articles__article_model", "publish_status"): ("publish_status_enum", "e"),
            ("articles__article_reaction_model", "reaction_kind"): (
                "article_reaction_kind_enum",
                "e",
            ),
            ("auth__user_model", "role"): ("role_enum", "e"),
            ("competency_matrix__competency_matrix_item_model", "grade"): ("grade_enum", "e"),
            ("competency_matrix__competency_matrix_item_model", "interview_frequency"): (
                "interview_frequency_enum",
                "e",
            ),
            ("competency_matrix__competency_matrix_item_model", "publish_status"): (
                "publish_status_enum",
                "e",
            ),
            ("competency_matrix__queued_question_model", "grade"): ("grade_enum", "e"),
            ("files__file_model", "purpose"): ("file_purpose_enum", "e"),
        }
        result = await self.db_session.execute(
            text(
                """
                SELECT
                    expected.table_name,
                    expected.column_name,
                    pg_type.typname AS type_name,
                    pg_type.typtype AS type_kind
                FROM (
                    VALUES
                        (
                            'articles__article_daily_analytics_model',
                            'source_category'
                        ),
                        ('articles__article_file_usage_model', 'usage'),
                        ('articles__article_model', 'publish_status'),
                        ('articles__article_reaction_model', 'reaction_kind'),
                        ('auth__user_model', 'role'),
                        (
                            'competency_matrix__competency_matrix_item_model',
                            'grade'
                        ),
                        (
                            'competency_matrix__competency_matrix_item_model',
                            'interview_frequency'
                        ),
                        (
                            'competency_matrix__competency_matrix_item_model',
                            'publish_status'
                        ),
                        ('competency_matrix__queued_question_model', 'grade'),
                        ('files__file_model', 'purpose')
                ) AS expected(table_name, column_name)
                JOIN pg_class
                    ON pg_class.relname = expected.table_name
                JOIN pg_namespace
                    ON pg_namespace.oid = pg_class.relnamespace
                    AND pg_namespace.nspname = current_schema()
                JOIN pg_attribute
                    ON pg_attribute.attrelid = pg_class.oid
                    AND pg_attribute.attname = expected.column_name
                    AND pg_attribute.attnum > 0
                    AND NOT pg_attribute.attisdropped
                JOIN pg_type
                    ON pg_type.oid = pg_attribute.atttypid
                """
            ),
        )

        actual = {
            (row["table_name"], row["column_name"]): (row["type_name"], row["type_kind"])
            for row in result.mappings()
        }

        assert actual == expected
