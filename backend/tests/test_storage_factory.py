"""
Testes para a factory de storage.

Valida seleção de provider via STORAGE_PROVIDER, comportamento singleton
e erro em provider desconhecido — sem dependência de Docker ou servidor real.
"""

import pytest

from app.services.storage.factory import get_storage_service, reset_storage_instances
from app.services.storage.seaweedfs_service import SeaweedFSService


@pytest.fixture(autouse=True)
def clear_factory_cache():
    """Limpa singletons do factory antes de cada teste."""
    reset_storage_instances()
    yield
    reset_storage_instances()


@pytest.fixture
def mock_seaweedfs_init(mocker):
    """Evita conexão real com SeaweedFS durante testes do factory."""
    mocker.patch.object(SeaweedFSService, "__init__", return_value=None)


class TestFactoryProviderSelection:
    def test_default_provider_is_seaweedfs(self, mocker, mock_seaweedfs_init):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "seaweedfs")
        svc = get_storage_service()
        assert isinstance(svc, SeaweedFSService)

    def test_seaweedfs_provider_explicit(self, mocker, mock_seaweedfs_init):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "SeaweedFS")
        svc = get_storage_service()
        assert isinstance(svc, SeaweedFSService)

    def test_minio_provider_selection(self, mocker):
        from app.services.minio_service import MinioService

        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "minio")
        mocker.patch.object(MinioService, "__init__", return_value=None)
        # patch get_minio_service para retornar instância sem conectar
        mock_instance = MinioService.__new__(MinioService)
        mocker.patch(
            "app.services.minio_service.get_minio_service",
            return_value=mock_instance,
        )
        svc = get_storage_service()
        assert isinstance(svc, MinioService)

    def test_invalid_provider_raises_value_error(self, mocker):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "s3_aws")
        with pytest.raises(ValueError, match="STORAGE_PROVIDER inválido"):
            get_storage_service()

    def test_empty_provider_raises_value_error(self, mocker):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "")
        with pytest.raises(ValueError, match="STORAGE_PROVIDER inválido"):
            get_storage_service()


class TestFactorySingleton:
    def test_same_instance_returned_on_repeated_calls(self, mocker, mock_seaweedfs_init):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "seaweedfs")
        svc1 = get_storage_service()
        svc2 = get_storage_service()
        assert svc1 is svc2

    def test_reset_clears_singleton(self, mocker, mock_seaweedfs_init):
        mocker.patch("app.services.storage.factory.settings.STORAGE_PROVIDER", "seaweedfs")
        svc1 = get_storage_service()
        reset_storage_instances()
        svc2 = get_storage_service()
        assert svc1 is not svc2
