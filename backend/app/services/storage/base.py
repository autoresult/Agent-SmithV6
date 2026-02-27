"""
StorageProvider - Interface abstrata para provedores de object storage.

Usa typing.Protocol (duck typing) para que implementações não precisem herdar
explicitamente desta classe.
"""

from io import BytesIO
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    """
    Contrato mínimo para qualquer provider de object storage.

    Implementações: SeaweedFSService, MinioService
    Seleção via factory: get_storage_service()
    """

    def upload_file(
        self,
        file_data: BinaryIO,
        company_id: str,
        document_id: str,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Faz upload com estrutura multi-tenant: {company_id}/{document_id}/{filename}

        Returns:
            object_name (caminho relativo dentro do bucket)
        """
        ...

    def upload_object(
        self,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        """
        Armazena bytes em um caminho arbitrário (sem estrutura company/document).
        Usado para salvar JSON raw, manifests e outros objetos internos.
        """
        ...

    def download_file(self, object_name: str) -> BytesIO:
        """
        Baixa um objeto pelo caminho completo.

        Returns:
            BytesIO com o conteúdo do arquivo
        """
        ...

    def delete_file(self, object_name: str) -> bool:
        """
        Remove um único objeto.

        Returns:
            True se removido com sucesso
        """
        ...

    def delete_folder(self, company_id: str, document_id: str) -> bool:
        """
        Remove todos os objetos com prefixo {company_id}/{document_id}/.

        Returns:
            True se removido com sucesso
        """
        ...

    def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """
        Gera URL pré-assinada para acesso temporário ao objeto.

        Args:
            expires: segundos de validade (padrão: 1 hora)

        Returns:
            URL pré-assinada
        """
        ...
