"""
Storage Factory - Seleciona o provider de object storage via STORAGE_PROVIDER.

Uso:
    from app.services.storage import get_storage_service

    storage = get_storage_service()   # SeaweedFS por padrão
    storage.upload_file(...)

Trocar provider: definir STORAGE_PROVIDER=minio no .env
"""

import logging
from typing import Dict

from ...core.config import settings
from .base import StorageProvider
from .seaweedfs_service import SeaweedFSService

logger = logging.getLogger(__name__)

# Singletons por provider (evita reconexão desnecessária)
_instances: Dict[str, StorageProvider] = {}


def get_storage_service() -> StorageProvider:
    """
    Retorna o provider de storage configurado em STORAGE_PROVIDER.

    Providers suportados:
        - "seaweedfs" (padrão) → SeaweedFSService via boto3
        - "minio"              → MinioService via minio SDK

    Returns:
        Instância singleton que satisfaz StorageProvider Protocol

    Raises:
        ValueError: se STORAGE_PROVIDER contiver valor desconhecido
    """
    provider = settings.STORAGE_PROVIDER.lower()

    if provider in _instances:
        return _instances[provider]

    if provider == "seaweedfs":
        # Instancia diretamente (factory gerencia o singleton via _instances)
        instance = SeaweedFSService()
        logger.info("Storage: SeaweedFSService (boto3 + S3 API)")

    elif provider == "minio":
        # Import lazy para não exigir minio SDK quando provider=seaweedfs
        from ..minio_service import get_minio_service

        instance = get_minio_service()
        logger.info("Storage: MinioService (minio SDK)")

    else:
        raise ValueError(
            f"STORAGE_PROVIDER inválido: '{settings.STORAGE_PROVIDER}'. "
            "Valores aceitos: 'seaweedfs', 'minio'."
        )

    _instances[provider] = instance
    return instance


def reset_storage_instances() -> None:
    """
    Limpa os singletons do factory.
    Necessário em testes para reinicializar com configurações diferentes.
    """
    global _instances
    _instances = {}
