from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import errors
from sqlalchemy import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    try:
        return os.environ["AVICOLA_TEST_DATABASE_URL"]
    except KeyError as exc:
        pytest.fail("AVICOLA_TEST_DATABASE_URL must reference a real empty PostgreSQL database")
        raise AssertionError from exc


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


EXPECTED_TABLES = {
    "alembic_version",
    "audit_events",
    "permissions",
    "role_permissions",
    "roles",
    "security_events",
    "sessions",
    "user_roles",
    "users",
    "company_profile",
    "currencies",
    "units_of_measure",
    "tax_rates",
    "stamps",
    "document_sequences",
    "payment_methods",
    "customers",
    "suppliers",
    "product_categories",
    "products",
    "farms",
    "houses",
    "warehouses",
    "inventory_lots",
    "inventory_documents",
    "inventory_document_lines",
    "inventory_movements",
    "inventory_balances",
    "inventory_cost_variances",
    "flocks",
    "flock_house_assignments",
    "flock_balances",
    "bird_movement_events",
    "mortality_events",
    "bird_adjustment_events",
    "flock_daily_records",
    "feed_consumption",
}


def _reset_schema() -> None:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")


@pytest.fixture(autouse=True)
def migrated_database() -> None:
    _reset_schema()


@pytest.mark.integration
def test_identity_migration_round_trip_on_real_postgresql() -> None:
    current = _run_alembic("current")

    assert "0005_production" in current.stdout

    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute("select version()")
        version = cursor.fetchone()
        cursor.execute("select table_name from information_schema.tables where table_schema = 'public'")
        tables = {row[0] for row in cursor.fetchall()}

    assert version is not None and version[0].startswith("PostgreSQL 16")
    assert tables == EXPECTED_TABLES

    _run_alembic("downgrade", "0001_baseline")
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute("select table_name from information_schema.tables where table_schema = 'public'")
        assert {row[0] for row in cursor.fetchall()} == {"alembic_version"}
    _run_alembic("upgrade", "head")


@pytest.mark.integration
def test_inventory_schema_has_reconciliation_indexes_and_append_only_trigger() -> None:
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute("select indexname from pg_indexes where schemaname = 'public'")
        indexes = {row[0] for row in cursor.fetchall()}
        assert {
            "ix_inventory_movements_bucket_occurred",
            "ix_inventory_movements_source",
            "uq_inventory_movements_reversal",
            "uq_inventory_balances_bucket",
        } <= indexes
        cursor.execute(
            "select tgname from pg_trigger where tgrelid = 'inventory_movements'::regclass and not tgisinternal"
        )
        assert "trg_inventory_movements_append_only" in {row[0] for row in cursor.fetchall()}


@pytest.mark.integration
def test_seed_is_complete_idempotent_and_grants_only_administrator() -> None:
    assert importlib.util.find_spec("avicola_pro.modules.identity.infrastructure.seed") is not None

    from avicola_pro.modules.identity.infrastructure.seed import (
        BASE_PERMISSION_KEYS,
        BASE_ROLE_CODES,
        seed_base_catalog,
    )

    engine = create_engine(_database_url())
    with engine.begin() as sa_connection:
        seed_base_catalog(sa_connection)
        seed_base_catalog(sa_connection)
    engine.dispose()

    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute("select key from permissions")
        permission_keys = {row[0] for row in cursor.fetchall()}
        cursor.execute("select code, is_system from roles")
        roles: dict[str, bool] = dict(cursor.fetchall())
        role_codes = set(roles)
        cursor.execute(
            """
            select r.code, count(rp.permission_id)
            from roles r
            left join role_permissions rp on rp.role_id = r.id
            group by r.code
            """
        )
        grant_counts: dict[str, int] = dict(cursor.fetchall())
        cursor.execute("select id from permissions union all select id from roles")
        seeded_ids = [row[0] for row in cursor.fetchall()]
        cursor.execute("select (select count(*) from users), (select count(*) from sessions)")
        sensitive_seed_counts = cursor.fetchone()

    assert permission_keys == set(BASE_PERMISSION_KEYS)
    assert role_codes == set(BASE_ROLE_CODES)
    assert all(roles.values())
    assert grant_counts["administrator"] == len(BASE_PERMISSION_KEYS)
    assert all(count == 0 for code, count in grant_counts.items() if code != "administrator")
    assert seeded_ids and all(identifier.version == 7 for identifier in seeded_ids)
    assert sensitive_seed_counts == (0, 0)


@pytest.mark.integration
def test_users_enforce_normalized_unique_identity_valid_state_and_restrictive_foreign_keys() -> None:
    user_id = uuid4()
    role_id = uuid4()
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute(
            """
            insert into users (id, username, email, display_name, password_hash)
            values (%s, 'operator', 'operator@example.test', 'Operator', 'argon2id-hash')
            """,
            (user_id,),
        )
        cursor.execute(
            """
            insert into roles (id, code, name, is_system)
            values (%s, 'temporary', 'Temporary', false)
            """,
            (role_id,),
        )
        cursor.execute("insert into user_roles (user_id, role_id) values (%s, %s)", (user_id, role_id))
        db_connection.commit()

        with pytest.raises(errors.UniqueViolation):
            cursor.execute(
                """
                insert into users (id, username, email, display_name, password_hash)
                values (%s, 'operator', 'other@example.test', 'Duplicate', 'argon2id-hash')
                """,
                (uuid4(),),
            )
        db_connection.rollback()

        with pytest.raises(errors.CheckViolation):
            cursor.execute(
                """
                insert into users (id, username, email, display_name, password_hash)
                values (%s, 'MixedCase', 'mixed@example.test', 'Mixed', 'argon2id-hash')
                """,
                (uuid4(),),
            )
        db_connection.rollback()

        with pytest.raises(errors.CheckViolation):
            cursor.execute(
                """
                insert into users (id, username, email, display_name, password_hash, status)
                values (%s, 'invalid-state', 'state@example.test', 'State', 'argon2id-hash', 'UNKNOWN')
                """,
                (uuid4(),),
            )
        db_connection.rollback()

        with pytest.raises(errors.ForeignKeyViolation):
            cursor.execute("delete from users where id = %s", (user_id,))
        db_connection.rollback()


@pytest.mark.integration
def test_sessions_store_only_hashes_and_enforce_expiration_order() -> None:
    columns_forbidden_from_sessions = {"token", "csrf_token", "password", "secret"}
    user_id = uuid4()
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = 'sessions'
            """
        )
        session_columns = {row[0] for row in cursor.fetchall()}
        assert columns_forbidden_from_sessions.isdisjoint(session_columns)
        assert {"token_hash", "csrf_hash", "family_id", "idle_expires_at", "absolute_expires_at"} <= session_columns

        cursor.execute(
            """
            insert into users (id, username, email, display_name, password_hash)
            values (%s, 'session-user', 'session@example.test', 'Session', 'argon2id-hash')
            """,
            (user_id,),
        )
        with pytest.raises(errors.CheckViolation):
            cursor.execute(
                """
                insert into sessions (
                    id, user_id, family_id, token_hash, csrf_hash,
                    idle_expires_at, absolute_expires_at
                ) values (
                    %s, %s, %s, %s, %s,
                    now() - interval '1 minute', now() + interval '1 hour'
                )
                """,
                (uuid4(), user_id, uuid4(), bytes(32), bytes(range(32))),
            )


@pytest.mark.integration
@pytest.mark.parametrize("table_name", ["audit_events", "security_events"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_event_ledgers_reject_update_and_delete_via_direct_sql(table_name: str, operation: str) -> None:
    event_id = uuid4()
    correlation_id = uuid4()
    statements = {
        ("audit_events", "update"): "update audit_events set outcome = 'FAILURE' where id = %s",
        ("audit_events", "delete"): "delete from audit_events where id = %s",
        ("security_events", "update"): "update security_events set outcome = 'FAILURE' where id = %s",
        ("security_events", "delete"): "delete from security_events where id = %s",
    }
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        if table_name == "audit_events":
            cursor.execute(
                """
                insert into audit_events (id, action, resource_type, outcome, correlation_id)
                values (%s, 'users.create', 'user', 'SUCCESS', %s)
                """,
                (event_id, correlation_id),
            )
        else:
            cursor.execute(
                """
                insert into security_events (id, event_type, outcome, correlation_id)
                values (%s, 'login.failed', 'FAILURE', %s)
                """,
                (event_id, correlation_id),
            )
        db_connection.commit()

        with pytest.raises(errors.RaiseException, match="append-only"):
            cursor.execute(statements[(table_name, operation)], (event_id,))


@pytest.mark.integration
def test_identity_and_event_indexes_cover_operational_queries() -> None:
    expected_indexes = {
        "ix_audit_events_actor_created_at",
        "ix_audit_events_correlation_id",
        "ix_audit_events_resource_created_at",
        "ix_security_events_actor_created_at",
        "ix_security_events_correlation_id",
        "ix_security_events_type_created_at",
        "ix_sessions_absolute_expires_at",
        "ix_sessions_family_active",
        "ix_sessions_idle_expires_at",
        "ix_sessions_user_active",
        "uq_permissions_key_ci",
        "uq_roles_code_ci",
        "uq_users_email_ci",
        "uq_users_username_ci",
    }
    with psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection, db_connection.cursor() as cursor:
        cursor.execute("select indexname from pg_indexes where schemaname = 'public'")
        actual_indexes = {row[0] for row in cursor.fetchall()}

    assert expected_indexes <= actual_indexes


@pytest.mark.integration
def test_event_payloads_accept_only_json_objects() -> None:
    with (
        psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection,
        db_connection.cursor() as cursor,
        pytest.raises(errors.CheckViolation),
    ):
        cursor.execute(
            """
            insert into security_events (id, event_type, outcome, correlation_id, metadata)
            values (%s, 'login.failed', 'FAILURE', %s, '["not", "an", "object"]'::jsonb)
            """,
            (uuid4(), uuid4()),
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "statement",
    [
        """
        insert into audit_events (id, action, resource_type, outcome, correlation_id, after_data)
        values (%s, 'users.update', 'user', 'FAILURE', %s, '{"password": "sensitive"}'::jsonb)
        """,
        """
        insert into security_events (id, event_type, outcome, correlation_id, metadata)
        values (%s, 'login.failed', 'FAILURE', %s, '{"password": "sensitive"}'::jsonb)
        """,
    ],
)
def test_event_payloads_reject_keys_outside_allowlist(statement: str) -> None:
    with (
        psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection,
        db_connection.cursor() as cursor,
        pytest.raises(errors.CheckViolation),
    ):
        cursor.execute(statement, (uuid4(), uuid4()))


@pytest.mark.integration
@pytest.mark.parametrize(
    "statement",
    [
        """
        insert into audit_events (id, action, resource_type, outcome, correlation_id, after_data)
        values (
            %s, 'users.update', 'user', 'FAILURE', %s,
            '{"username": {"password": "sensitive"}}'::jsonb
        )
        """,
        """
        insert into audit_events (id, action, resource_type, outcome, correlation_id, before_data)
        values (%s, 'roles.update', 'role', 'FAILURE', %s, '{"role_id": ["first", "second"]}'::jsonb)
        """,
        """
        insert into security_events (id, event_type, outcome, correlation_id, metadata)
        values (%s, 'login.failed', 'FAILURE', %s, '{"reason": {"token": "sensitive"}}'::jsonb)
        """,
        """
        insert into security_events (id, event_type, outcome, correlation_id, metadata)
        values (%s, 'authorization.denied', 'DENIED', %s, '{"resource_id": ["first", "second"]}'::jsonb)
        """,
    ],
)
def test_event_payloads_reject_objects_and_arrays_under_allowlisted_keys(statement: str) -> None:
    with (
        psycopg.connect(_database_url().replace("+psycopg", "")) as db_connection,
        db_connection.cursor() as cursor,
        pytest.raises(errors.CheckViolation),
    ):
        cursor.execute(statement, (uuid4(), uuid4()))
