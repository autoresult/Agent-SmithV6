"""
SeaweedFS Service - Object storage via API S3-compatível do SeaweedFS.

Usa boto3 com path-style addressing (obrigatório no SeaweedFS).
Porta padrão S3: 8333
"""

import logging
from io import BytesIO
from typing import BinaryIO, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ...core.config import settings

logger = logging.getLogger(__name__)


class SeaweedFSService:
    """
    Provider de object storage usando SeaweedFS (API S3-compatível via boto3).

    Estrutura de objetos no bucket:
        {company_id}/{document_id}/{filename}   ← arquivos originais
        {company_id}/raw/{document_id}.json     ← JSON extraído (Bronze Layer)
    """

    def __init__(self):
        endpoint = settings.SEAWEEDFS_ENDPOINT
        secure = settings.SEAWEEDFS_SECURE
        self.bucket_name = settings.SEAWEEDFS_BUCKET

        # boto3 requer URL completa; SeaweedFS exige path-style addressing
        self.client = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if secure else ''}://{endpoint}",
            aws_access_key_id=settings.SEAWEEDFS_ACCESS_KEY,
            aws_secret_access_key=settings.SEAWEEDFS_SECRET_KEY,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}),
        )

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Cria o bucket se não existir."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' já existe")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("404", "NoSuchBucket"):
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' criado com sucesso")
            else:
                logger.error(f"Erro ao verificar bucket: {e}")
                raise

    def upload_file(
        self,
        file_data: BinaryIO,
        company_id: str,
        document_id: str,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload com estrutura multi-tenant: {company_id}/{document_id}/{filename}

        Returns:
            object_name (caminho relativo dentro do bucket)
        """
        object_name = f"{company_id}/{document_id}/{filename}"

        try:
            if not isinstance(file_data, BytesIO):
                file_bytes = file_data.read()
                file_data = BytesIO(file_bytes)

            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=file_data,
                ContentLength=file_size,
                ContentType=content_type,
            )

            logger.info(f"Arquivo enviado: {object_name} ({file_size} bytes)")
            return object_name

        except ClientError as e:
            logger.error(f"Erro ao fazer upload do arquivo: {e}")
            raise

    def upload_object(
        self,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        """
        Armazena bytes em caminho arbitrário (sem estrutura company/document).
        Usado para JSON raw, manifests e outros objetos internos.
        """
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=data,
                ContentLength=length,
                ContentType=content_type,
            )
            logger.info(f"Objeto armazenado: {object_name} ({length} bytes)")

        except ClientError as e:
            logger.error(f"Erro ao armazenar objeto: {e}")
            raise

    def download_file(self, object_name: str) -> BytesIO:
        """
        Download de objeto pelo caminho completo.

        Returns:
            BytesIO com conteúdo do arquivo
        """
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name, Key=object_name
            )
            file_data = BytesIO(response["Body"].read())
            logger.info(f"Arquivo baixado: {object_name}")
            return file_data

        except ClientError as e:
            logger.error(f"Erro ao fazer download do arquivo: {e}")
            raise

    def delete_file(self, object_name: str) -> bool:
        """Remove um único objeto."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Arquivo deletado: {object_name}")
            return True

        except ClientError as e:
            logger.error(f"Erro ao deletar arquivo: {e}")
            return False

    def delete_folder(self, company_id: str, document_id: str) -> bool:
        """
        Remove todos os objetos com prefixo {company_id}/{document_id}/.
        Usa paginação para lidar com pastas com muitos arquivos.
        """
        prefix = f"{company_id}/{document_id}/"

        try:
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                for obj in page.get("Contents", []):
                    objects_to_delete.append({"Key": obj["Key"]})

            if objects_to_delete:
                self.client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={"Objects": objects_to_delete},
                )

            logger.info(f"Pasta deletada: {prefix} ({len(objects_to_delete)} objetos)")
            return True

        except ClientError as e:
            logger.error(f"Erro ao deletar pasta: {e}")
            return False

    def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """
        Gera URL pré-assinada para acesso temporário.

        Args:
            expires: segundos de validade (padrão: 1 hora)

        Returns:
            URL pré-assinada
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expires,
            )
            return url

        except ClientError as e:
            logger.error(f"Erro ao gerar URL pré-assinada: {e}")
            raise


# Singleton interno — acesso via factory, não diretamente
_seaweedfs_service: Optional[SeaweedFSService] = None


def get_seaweedfs_service() -> SeaweedFSService:
    """Retorna instância singleton do SeaweedFSService."""
    global _seaweedfs_service
    if _seaweedfs_service is None:
        _seaweedfs_service = SeaweedFSService()
    return _seaweedfs_service
