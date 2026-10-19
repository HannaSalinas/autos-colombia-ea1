from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app import check_db, config
from app.database import create_database_engine


@pytest.fixture
def configured_env(tmp_path, monkeypatch):
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_CONNECT_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DB_HOST=127.0.0.1\nDB_PORT=5432\nDB_NAME=test_db\n"
        "DB_USER=test_user\nDB_PASSWORD='example@:/#${literal}'\nDB_CONNECT_TIMEOUT=5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    return env_file


def test_env_path_is_absolute():
    assert config.ENV_FILE.is_absolute()
    assert config.ENV_FILE.parent.name == "backend"


def test_configuration_ignores_working_directory(configured_env, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    settings = config.load_database_settings()
    assert settings.name == "test_db"
    assert settings.password == "example@:/#${literal}"
    assert settings.password not in repr(settings)


def test_environment_overrides_file(configured_env, monkeypatch):
    monkeypatch.setenv("DB_NAME", "override_db")
    assert config.load_database_settings().name == "override_db"


def test_placeholder_does_not_attempt_connection(configured_env, monkeypatch, capsys):
    monkeypatch.setenv("DB_PASSWORD", "CAMBIAR_PASSWORD")
    factory = MagicMock()
    monkeypatch.setattr(check_db, "create_database_engine", factory)
    assert check_db.main() == 2
    factory.assert_not_called()
    assert "DB_PASSWORD" in capsys.readouterr().err


def test_invalid_port_does_not_expose_value(configured_env, monkeypatch, capsys):
    monkeypatch.setenv("DB_PORT", "private-invalid-value")
    assert check_db.main() == 2
    output = capsys.readouterr().err
    assert "DB_PORT" in output
    assert "private-invalid-value" not in output


def test_url_preserves_special_characters(configured_env):
    settings = config.load_database_settings()
    engine = create_database_engine(settings)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.password == settings.password
        assert engine.echo is False
        assert engine.hide_parameters is True
    finally:
        engine.dispose()


def test_check_executes_only_select_one(configured_env, monkeypatch, capsys):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    monkeypatch.setattr(check_db, "create_database_engine", lambda settings: engine)
    assert check_db.main() == 0
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    engine.dispose.assert_called_once()
    assert "SELECT 1 correcto" in capsys.readouterr().out


def test_connection_failure_does_not_expose_driver_error(configured_env, monkeypatch, capsys):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("private-driver-value"))
    monkeypatch.setattr(check_db, "create_database_engine", lambda settings: engine)
    assert check_db.main() == 1
    output = capsys.readouterr()
    assert "private-driver-value" not in output.out + output.err
    assert "No se pudo conectar" in output.err
    engine.dispose.assert_called_once()
