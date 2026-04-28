from app.core.config import Settings, parse_bool


def test_sqlalchemy_echo_is_disabled_by_default(monkeypatch):
    """Confirm SQL query logging is opt-in to avoid leaking sensitive values.

    Args:
        monkeypatch: Pytest fixture used to isolate environment variables.

    Returns:
        None.

    Side effects:
        Temporarily removes `SQLALCHEMY_ECHO` from the test environment.
    """
    monkeypatch.delenv("SQLALCHEMY_ECHO", raising=False)

    settings = Settings()

    assert settings.SQLALCHEMY_ECHO is False


def test_sqlalchemy_echo_can_be_enabled_explicitly(monkeypatch):
    """Confirm developers can opt into SQL query logging locally.

    Args:
        monkeypatch: Pytest fixture used to isolate environment variables.

    Returns:
        None.

    Side effects:
        Temporarily sets `SQLALCHEMY_ECHO` in the test environment.
    """
    monkeypatch.setenv("SQLALCHEMY_ECHO", "true")

    settings = Settings()

    assert settings.SQLALCHEMY_ECHO is True


def test_parse_bool_accepts_common_truthy_values():
    """Validate accepted truthy values for environment booleans.

    Returns:
        None.

    Side effects:
        None.
    """
    assert parse_bool("1") is True
    assert parse_bool("true") is True
    assert parse_bool("YES") is True
    assert parse_bool("on") is True


def test_parse_bool_rejects_unknown_values():
    """Validate unknown boolean strings fail closed.

    Returns:
        None.

    Side effects:
        None.
    """
    assert parse_bool("false") is False
    assert parse_bool("0") is False
    assert parse_bool("unexpected") is False
