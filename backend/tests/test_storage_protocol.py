"""
Testes de conformidade com o StorageProvider Protocol.

Verifica que SeaweedFSService e MinioService satisfazem o contrato
definido em storage/base.py via isinstance() com runtime_checkable.
"""

import pytest

from app.services.storage.base import StorageProvider
from app.services.storage.seaweedfs_service import SeaweedFSService
from app.services.minio_service import MinioService


def _make_seaweedfs(mocker) -> SeaweedFSService:
    """Instância de SeaweedFSService sem inicialização real."""
    mocker.patch.object(SeaweedFSService, "__init__", return_value=None)
    svc = SeaweedFSService.__new__(SeaweedFSService)
    return svc


def _make_minio(mocker) -> MinioService:
    """Instância de MinioService sem inicialização real."""
    mocker.patch.object(MinioService, "__init__", return_value=None)
    svc = MinioService.__new__(MinioService)
    return svc


REQUIRED_METHODS = [
    "upload_file",
    "upload_object",
    "download_file",
    "delete_file",
    "delete_folder",
    "get_file_url",
]


class TestSeaweedFSProtocolConformance:
    def test_isinstance_storage_provider(self, mocker):
        svc = _make_seaweedfs(mocker)
        assert isinstance(svc, StorageProvider)

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, mocker, method):
        svc = _make_seaweedfs(mocker)
        assert hasattr(svc, method), f"SeaweedFSService está faltando o método: {method}"
        assert callable(getattr(svc, method))


class TestMinioProtocolConformance:
    def test_isinstance_storage_provider(self, mocker):
        svc = _make_minio(mocker)
        assert isinstance(svc, StorageProvider)

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, mocker, method):
        svc = _make_minio(mocker)
        assert hasattr(svc, method), f"MinioService está faltando o método: {method}"
        assert callable(getattr(svc, method))
