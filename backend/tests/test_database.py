from app.database import _ensure_sqlite_parent


def test_sqlite_parent_directory_is_created(tmp_path) -> None:
    database_path = tmp_path / "missing" / "nested" / "app.db"

    _ensure_sqlite_parent(f"sqlite:///{database_path.as_posix()}")

    assert database_path.parent.exists()
