import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "1e86b9128fba_add_design_customer_ownership.py"
)


def load_migration():
    """Load the Design ownership migration module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "design_ownership_migration",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScalarResult:
    """Minimal SQLAlchemy result stub for migration guard tests."""

    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        """Return the configured scalar count."""
        return self.value


class FakeBind:
    """Record migration guard queries and return a Design row count."""

    def __init__(self, existing_design_count: int) -> None:
        self.existing_design_count = existing_design_count
        self.queries: list[str] = []

    def execute(self, statement):
        """Record one query and return the configured count."""
        self.queries.append(str(statement))
        return ScalarResult(self.existing_design_count)


class FakeOperations:
    """Record Alembic operations without mutating a database."""

    def __init__(self, existing_design_count: int = 0) -> None:
        self.bind = FakeBind(existing_design_count)
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_bind(self):
        """Return the fake migration connection."""
        return self.bind

    def f(self, name: str) -> str:
        """Return an Alembic-formatted name unchanged."""
        return name

    def __getattr__(self, name: str):
        """Record one dynamic Alembic operation."""

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def test_design_ownership_migration_upgrade_adds_required_owner_schema(monkeypatch):
    migration = load_migration()
    operations = FakeOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert operations.bind.queries == ["SELECT count(*) FROM designs"]
    assert [call[0] for call in operations.calls] == [
        "add_column",
        "create_index",
        "create_foreign_key",
    ]
    added_column = operations.calls[0][1][1]
    assert added_column.name == "customer_id"
    assert added_column.nullable is False
    assert operations.calls[1][1] == (
        "ix_designs_customer_id",
        "designs",
        ["customer_id"],
    )
    assert operations.calls[2][1] == (
        "fk_designs_customer_id_users",
        "designs",
        "users",
        ["customer_id"],
        ["id"],
    )


def test_design_ownership_migration_stops_before_ddl_for_existing_rows(monkeypatch):
    migration = load_migration()
    operations = FakeOperations(existing_design_count=1)
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match="backfill explicit customer ownership"):
        migration.upgrade()

    assert operations.bind.queries == ["SELECT count(*) FROM designs"]
    assert operations.calls == []


def test_design_ownership_migration_downgrade_removes_owner_schema(monkeypatch):
    migration = load_migration()
    operations = FakeOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    assert [call[0] for call in operations.calls] == [
        "drop_constraint",
        "drop_index",
        "drop_column",
    ]
    assert operations.calls[0][1] == (
        "fk_designs_customer_id_users",
        "designs",
    )
    assert operations.calls[0][2] == {"type_": "foreignkey"}
    assert operations.calls[2][1] == ("designs", "customer_id")
