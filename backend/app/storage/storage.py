from pathlib import Path
from app.storage.base import BaseStorageAdapter
from app.storage.factory import get_storage_adapter
from app.storage.local import LocalStorageAdapter


class StorageService(LocalStorageAdapter):
    """
    Storage Service with full backwards-compatibility.
    Acts as default LocalStorageAdapter unless instantiated via factory.
    """
    pass


__all__ = ["BaseStorageAdapter", "LocalStorageAdapter", "StorageService", "get_storage_adapter"]
