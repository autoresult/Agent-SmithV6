"""
Storage Package - Abstração de object storage com factory pattern.

Uso principal:
    from app.services.storage import get_storage_service, StorageProvider

    storage: StorageProvider = get_storage_service()
    storage.upload_file(...)

Provider selecionado via STORAGE_PROVIDER no .env:
    STORAGE_PROVIDER=seaweedfs  (padrão)
    STORAGE_PROVIDER=minio
"""

from .base import StorageProvider
from .factory import get_storage_service, reset_storage_instances
from .seaweedfs_service import SeaweedFSService

__all__ = [
    "StorageProvider",
    "SeaweedFSService",
    "get_storage_service",
    "reset_storage_instances",
]
