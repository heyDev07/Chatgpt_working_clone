"""add sql_demo schema for text-to-sql tool

Revision ID: 0eb2d0957976
Revises: 1316cdf293dd
Create Date: 2026-07-24 19:37:10.171765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config.settings import get_settings

# revision identifiers, used by Alembic.
revision: str = '0eb2d0957976'
down_revision: Union[str, None] = '1316cdf293dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A self-contained sample dataset for the text-to-SQL tool to query, deliberately kept out of
    # `app.models`/Base.metadata - this schema is a fixed demo target for LLM-generated SELECTs,
    # not part of the application's own data model, so it has no ORM models and isn't touched by
    # autogenerate.
    op.execute("CREATE SCHEMA IF NOT EXISTS sql_demo")

    op.execute(
        """
        CREATE TABLE sql_demo.departments (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sql_demo.employees (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            department_id INTEGER NOT NULL REFERENCES sql_demo.departments(id),
            salary NUMERIC(10, 2) NOT NULL,
            hire_date DATE NOT NULL
        )
        """
    )

    op.execute(
        """
        INSERT INTO sql_demo.departments (name) VALUES
            ('Engineering'), ('Sales'), ('Marketing'), ('Finance')
        """
    )
    op.execute(
        """
        INSERT INTO sql_demo.employees (name, department_id, salary, hire_date) VALUES
            ('Alice Chen', 1, 165000, '2021-03-14'),
            ('Bilal Hussain', 1, 148000, '2022-07-01'),
            ('Carla Gomez', 1, 172500, '2019-11-20'),
            ('Devon Ito', 1, 133000, '2023-02-08'),
            ('Elena Petrova', 2, 98000, '2020-06-15'),
            ('Frank Osei', 2, 112000, '2021-09-30'),
            ('Grace Lindqvist', 2, 87000, '2023-05-11'),
            ('Hiro Tanaka', 3, 91000, '2022-01-19'),
            ('Isabel Duarte', 3, 76000, '2023-08-01'),
            ('Jamal Carter', 4, 121000, '2018-04-25'),
            ('Kavya Reddy', 4, 138000, '2020-10-05'),
            ('Liam O''Brien', 4, 105000, '2022-12-12')
        """
    )

    # Defense in depth: the tool-layer validation (SELECT-only, single-statement, no dangerous
    # keywords) is one layer, but a bug there shouldn't be the only thing standing between
    # LLM-generated SQL and the app's real tables (users, refresh_tokens, etc). A dedicated role
    # that can only SELECT from this one schema makes that a database-enforced guarantee instead
    # of a code-review one.
    password = get_settings().sql_demo_db_password
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sql_demo_reader') THEN
                CREATE ROLE sql_demo_reader WITH LOGIN PASSWORD '{password}';
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA sql_demo TO sql_demo_reader")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA sql_demo TO sql_demo_reader")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA sql_demo GRANT SELECT ON TABLES TO sql_demo_reader"
    )
    # Postgres roles are cluster-wide, not per-database - without this, sql_demo_reader could
    # still connect to and enumerate other databases on the same server.
    op.execute("REVOKE ALL ON SCHEMA public FROM sql_demo_reader")


def downgrade() -> None:
    op.execute("DROP OWNED BY sql_demo_reader")
    op.execute("DROP ROLE IF EXISTS sql_demo_reader")
    op.execute("DROP SCHEMA IF EXISTS sql_demo CASCADE")
