import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "68a133510971_add_template_product_pricing_anchor.py"
)


def load_migration():
    """Load the Template Product migration module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "template_product_migration",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScalarResult:
    """Minimal scalar result used by migration operation stubs."""

    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        """Return the configured Template row count."""
        return self.value


class FakeBind:
    """Record migration guard queries and return a Template row count."""

    def __init__(self, existing_template_count: int) -> None:
        self.existing_template_count = existing_template_count
        self.queries: list[str] = []

    def execute(self, statement):
        """Record one guard query and return the configured count."""
        self.queries.append(str(statement))
        return ScalarResult(self.existing_template_count)


class FakeOperations:
    """Record Alembic operations without mutating a database."""

    def __init__(self, existing_template_count: int = 0) -> None:
        self.bind = FakeBind(existing_template_count)
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


def test_template_product_migration_adds_required_pricing_anchor(monkeypatch):
    migration = load_migration()
    operations = FakeOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert operations.bind.queries == ["SELECT count(*) FROM templates"]
    assert [call[0] for call in operations.calls] == [
        "add_column",
        "create_index",
        "create_foreign_key",
    ]
    added_column = operations.calls[0][1][1]
    assert added_column.name == "product_id"
    assert added_column.nullable is False
    assert operations.calls[2][1] == (
        "fk_templates_product_id_products",
        "templates",
        "products",
        ["product_id"],
        ["id"],
    )


def test_template_product_migration_stops_before_ddl_for_existing_rows(monkeypatch):
    migration = load_migration()
    operations = FakeOperations(existing_template_count=1)
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match="backfill explicit Product mappings"):
        migration.upgrade()

    assert operations.calls == []


def test_template_product_migration_downgrade_removes_pricing_anchor(monkeypatch):
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
        "fk_templates_product_id_products",
        "templates",
    )
    assert operations.calls[2][1] == ("templates", "product_id")
