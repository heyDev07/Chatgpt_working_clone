"""Unit tests for the pure, dependency-free security functions added during Phase 15's
hardening pass and the Phase 6 calculator sandbox - no DB/Redis/network needed, so these run
in plain CI without the docker-compose infra this project otherwise relies on for everything
else. Broader integration coverage against real infra is Phase 19's job, not this file's."""

import pytest

from app.storage.s3_client import safe_storage_filename
from app.tools.calculator import evaluate_expression
from app.tools.sql_query import validate_readonly_sql


class TestSafeStorageFilename:
    def test_strips_path_traversal(self):
        assert safe_storage_filename("../../etc/passwd") == "passwd"

    def test_strips_directory_components(self):
        assert safe_storage_filename("a/b/c.txt") == "c.txt"

    def test_replaces_unsafe_characters(self):
        # Each disallowed character is replaced individually, not collapsed - a space followed
        # by "(" becomes two underscores, not one.
        assert safe_storage_filename("my file (final).png") == "my_file__final_.png"

    def test_falls_back_on_empty_result(self):
        assert safe_storage_filename("....") == "file"
        assert safe_storage_filename("") == "file"

    def test_truncates_long_names(self):
        result = safe_storage_filename("x" * 300 + ".png")
        assert len(result) <= 200


class TestEvaluateExpression:
    def test_basic_arithmetic(self):
        assert evaluate_expression("(2 + 3) * 4") == 20

    def test_rejects_name_nodes(self):
        with pytest.raises(ValueError):
            evaluate_expression("__import__('os')")

    def test_rejects_call_nodes(self):
        with pytest.raises(ValueError):
            evaluate_expression("print(1)")

    def test_division_by_zero(self):
        with pytest.raises(ValueError):
            evaluate_expression("1 / 0")

    def test_rejects_oversized_exponent(self):
        with pytest.raises(ValueError):
            evaluate_expression("2 ** 100000")


class TestValidateReadonlySql:
    def test_accepts_plain_select(self):
        result = validate_readonly_sql("SELECT * FROM sql_demo.employees")
        assert result.startswith("SELECT")
        assert "LIMIT" in result  # auto-appended when the query didn't specify one

    def test_rejects_non_select(self):
        with pytest.raises(ValueError):
            validate_readonly_sql("DROP TABLE sql_demo.employees")

    def test_rejects_multiple_statements(self):
        with pytest.raises(ValueError):
            validate_readonly_sql("SELECT 1; DROP TABLE employees")

    def test_rejects_sql_comments(self):
        with pytest.raises(ValueError):
            validate_readonly_sql("SELECT * FROM employees -- comment")

    def test_preserves_existing_limit(self):
        result = validate_readonly_sql("SELECT * FROM sql_demo.employees LIMIT 5")
        assert result.count("LIMIT") == 1
