import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

MIGRATION_DIRECTORY = Path(__file__).parents[1] / "alembic" / "versions"
EXPAND_MIGRATION_PATH = (
    MIGRATION_DIRECTORY / "838722b0b76e_add_payment_provider_identity_and_.py"
)
CONTRACT_MIGRATION_PATH = (
    MIGRATION_DIRECTORY / "d98b7e31a3a3_enforce_payment_provider_identity.py"
)


def load_migration(path: Path, module_name: str):
    """Load one Payment provider identity migration from its file path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def create_legacy_payment_schema(connection) -> None:
    """Create the representative pre-#200 Payment and replay tables."""
    connection.execute(
        text(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                status VARCHAR(32) NOT NULL,
                payment_provider_reference VARCHAR(255),
                payment_verified_at DATETIME
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE payments (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                status VARCHAR(32) NOT NULL,
                amount NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                payment_provider_reference VARCHAR(255),
                verified_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE payment_webhook_events (
                id INTEGER PRIMARY KEY,
                event_id VARCHAR(255) NOT NULL UNIQUE,
                source VARCHAR(64) NOT NULL,
                order_id INTEGER,
                payment_id INTEGER,
                received_at DATETIME NOT NULL
            )
            """
        )
    )


def test_expand_migration_backfills_and_preserves_representative_legacy_data(
    monkeypatch,
):
    """Prove expand migration preserves verified, active, and replay history."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        create_legacy_payment_schema(connection)
        connection.execute(
            text(
                """
                INSERT INTO orders (
                    id, status, payment_provider_reference, payment_verified_at
                ) VALUES
                    (
                        70, 'confirmed', 'trusted-transaction',
                        '2026-07-20 12:00:00'
                    ),
                    (80, 'draft', NULL, NULL)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO payments (
                    id, order_id, status, amount, currency,
                    payment_provider_reference, verified_at,
                    created_at, updated_at
                ) VALUES
                    (
                        7, 70, 'verified', 59.50, 'COP', 'trusted-transaction',
                        '2026-07-20 12:00:00', '2026-07-20 11:00:00',
                        '2026-07-20 12:00:00'
                    ),
                    (
                        8, 80, 'initiated', 20.00, 'COP', NULL, NULL,
                        '2026-07-21 10:00:00', '2026-07-21 10:00:00'
                    )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO payment_webhook_events (
                    id, event_id, source, order_id, payment_id, received_at
                ) VALUES (
                    3, 'legacy-replay-event', 'payment_provider_webhook',
                    70, 7, '2026-07-20 12:00:00'
                )
                """
            )
        )

        migration = load_migration(
            EXPAND_MIGRATION_PATH,
            "payment_provider_identity_expand_migration",
        )
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()

        payments = connection.execute(
            text(
                """
                SELECT id, provider_code, merchant_reference,
                       payment_provider_reference, verified_at
                FROM payments
                ORDER BY id
                """
            )
        ).mappings()
        assert [dict(payment) for payment in payments] == [
            {
                "id": 7,
                "provider_code": "legacy_generic",
                "merchant_reference": "legacy-payment-7",
                "payment_provider_reference": "trusted-transaction",
                "verified_at": "2026-07-20 12:00:00",
            },
            {
                "id": 8,
                "provider_code": "legacy_generic",
                "merchant_reference": "legacy-payment-8",
                "payment_provider_reference": None,
                "verified_at": None,
            },
        ]
        orders = connection.execute(
            text(
                """
                SELECT id, status, payment_provider_reference,
                       payment_verified_at
                FROM orders
                ORDER BY id
                """
            )
        ).mappings()
        assert [dict(order) for order in orders] == [
            {
                "id": 70,
                "status": "confirmed",
                "payment_provider_reference": "trusted-transaction",
                "payment_verified_at": "2026-07-20 12:00:00",
            },
            {
                "id": 80,
                "status": "draft",
                "payment_provider_reference": None,
                "payment_verified_at": None,
            },
        ]
        replay_event = (
            connection.execute(
                text(
                    """
                SELECT event_id, order_id, payment_id
                FROM payment_webhook_events
                """
                )
            )
            .mappings()
            .one()
        )
        assert dict(replay_event) == {
            "event_id": "legacy-replay-event",
            "order_id": 70,
            "payment_id": 7,
        }
        inspector = inspect(connection)
        assert inspector.has_table("payment_provider_transactions")
        assert inspector.has_table("payment_provider_events")
        assert (
            connection.execute(
                text("SELECT count(*) FROM payment_provider_transactions")
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM payment_provider_events")
            ).scalar_one()
            == 0
        )


class ScalarResult:
    """Minimal scalar result for contract migration guard tests."""

    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        """Return the configured guard count."""
        return self.value


class FakeBind:
    """Record contract guard queries and return configured counts."""

    def __init__(self, counts: list[int]) -> None:
        self.counts = iter(counts)
        self.queries: list[str] = []

    def execute(self, statement):
        """Record one query and return its configured scalar count."""
        self.queries.append(str(statement))
        return ScalarResult(next(self.counts))


class FakeOperations:
    """Record contract migration operations after guard validation."""

    def __init__(self, counts: list[int]) -> None:
        self.bind = FakeBind(counts)
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_bind(self):
        """Return the fake migration connection."""
        return self.bind

    def __getattr__(self, name: str):
        """Record one dynamic Alembic operation."""

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def test_contract_migration_enforces_constraints_after_clean_preflight(monkeypatch):
    """Apply required identity constraints only after both guards pass."""
    migration = load_migration(
        CONTRACT_MIGRATION_PATH,
        "payment_provider_identity_contract_migration",
    )
    operations = FakeOperations([0, 0])
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert len(operations.bind.queries) == 2
    assert [call[0] for call in operations.calls] == [
        "alter_column",
        "alter_column",
        "create_unique_constraint",
    ]
    assert operations.calls[0][1][:2] == ("payments", "provider_code")
    assert operations.calls[1][1][:2] == ("payments", "merchant_reference")
    assert operations.calls[2][1] == (
        "uq_payments_provider_merchant_reference",
        "payments",
        ["provider_code", "merchant_reference"],
    )


@pytest.mark.parametrize(
    ("counts", "message", "expected_query_count"),
    [
        ([1], "backfill or writer compatibility is incomplete", 1),
        ([0, 1], "Duplicate Payment provider identities exist", 2),
    ],
)
def test_contract_migration_refuses_unsafe_identity_data(
    counts,
    message,
    expected_query_count,
    monkeypatch,
):
    """Stop before DDL when identity preflight detects unsafe data."""
    migration = load_migration(
        CONTRACT_MIGRATION_PATH,
        "unsafe_payment_provider_identity_contract_migration",
    )
    operations = FakeOperations(counts)
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match=message):
        migration.upgrade()

    assert len(operations.bind.queries) == expected_query_count
    assert operations.calls == []
