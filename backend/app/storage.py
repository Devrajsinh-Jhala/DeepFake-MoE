from pathlib import Path

from cryptography.fernet import Fernet

from .config import Settings, get_settings

_PROCESS_FERNET_KEY = Fernet.generate_key()


class EncryptedBlobStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.data_dir / "blobs"
        self.root.mkdir(parents=True, exist_ok=True)
        key = self.settings.encryption_key.encode("utf-8") if self.settings.encryption_key else _PROCESS_FERNET_KEY
        self._fernet = Fernet(key)

    def path_for(self, analysis_id: str) -> Path:
        return self.root / f"{analysis_id}.enc"

    def save(self, analysis_id: str, payload: bytes) -> Path:
        encrypted = self._fernet.encrypt(payload)
        path = self.path_for(analysis_id)
        path.write_bytes(encrypted)
        return path

    def read(self, path: str | Path) -> bytes:
        encrypted = Path(path).read_bytes()
        return self._fernet.decrypt(encrypted)

    def delete(self, path: str | Path | None) -> None:
        if not path:
            return
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def cleanup_paths(self, paths: list[str]) -> None:
        for path in paths:
            self.delete(path)
