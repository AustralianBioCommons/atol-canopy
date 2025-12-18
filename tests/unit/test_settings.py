from app.core.settings import Settings


def test_settings_builds_database_uri_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "testuser")
    monkeypatch.setenv("POSTGRES_PASSWORD", "testpass")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    monkeypatch.setenv("DATABASE_URI", "postgresql://testuser:testpass@localhost:5432/testdb")

    settings = Settings()

    assert settings.DATABASE_URI == "postgresql://testuser:testpass@localhost:5432/testdb"
    assert settings.POSTGRES_USER == "testuser"
    assert settings.POSTGRES_PASSWORD == "testpass"
    assert settings.POSTGRES_SERVER == "localhost"
    assert settings.POSTGRES_PORT == "5432"
    assert settings.POSTGRES_DB == "testdb"
    assert settings.DATABASE_URI == "postgresql://testuser:testpass@localhost:5432/testdb"
