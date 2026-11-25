import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

# Only allow safe UUID-like / alphanumeric storage keys (prevents path traversal)
_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageBackend(ABC):
    """Abstract storage interface so LocalDisk can be swapped with Cloudflare R2 / AWS S3."""

    @abstractmethod
    def append_chunk(self, storage_key: str, data: bytes) -> int:
        """Append bytes to a file and return new total size."""

    @abstractmethod
    def write_bytes(self, storage_key: str, data: bytes) -> int:
        """Write complete bytes to a new file and return total size."""

    @abstractmethod
    def get_local_path(self, storage_key: str) -> Path:
        """Return safe resolved path for streaming or FFmpeg inspection."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete object if it exists."""


class LocalDiskStorage(StorageBackend):
    def __init__(self, root_dir: str | Path) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, storage_key: str) -> Path:
        if not _SAFE_KEY_RE.match(storage_key) or ".." in storage_key:
            raise ValueError("Invalid storage key.")
        resolved = (self.root / storage_key).resolve()
        if resolved.parent != self.root:
            raise ValueError("Path traversal detected.")
        return resolved

    def append_chunk(self, storage_key: str, data: bytes) -> int:
        target = self._safe_path(storage_key)
        with open(target, "ab") as f:
            f.write(data)
        return target.stat().st_size

    def write_bytes(self, storage_key: str, data: bytes) -> int:
        target = self._safe_path(storage_key)
        with open(target, "wb") as f:
            f.write(data)
        return target.stat().st_size

    def get_local_path(self, storage_key: str) -> Path:
        target = self._safe_path(storage_key)
        if not target.exists():
            raise FileNotFoundError(f"Storage object not found: {storage_key}")
        return target

    def delete(self, storage_key: str) -> None:
        target = self._safe_path(storage_key)
        if target.exists():
            os.remove(target)


_storage_instance: StorageBackend = LocalDiskStorage(settings.STORAGE_LOCAL_ROOT)


def get_storage() -> StorageBackend:
    return _storage_instance