"""
Integration tests for SeaweedFS S3 storage — Upload, download, delete, list.

Requer:
- Docker disponível (Testcontainers)
- chrislusf/seaweedfs:latest image

Usa boto3 com path-style addressing diretamente no container.
Testa as operações de storage S3 que o SeaweedFSService encapsula.
"""

import io
import uuid

import pytest


# ===========================================================================
# TestStorageUploadDownload
# ===========================================================================


class TestStorageUploadDownload:

    def test_upload_text_file(self, s3_client):
        """Upload de arquivo texto deve completar sem erro."""
        client, bucket = s3_client
        key = f"test/{uuid.uuid4()}/hello.txt"
        content = b"Hello, SeaweedFS!"

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(content),
            ContentLength=len(content),
            ContentType="text/plain",
        )

        # Verificar que o objeto existe via head_object
        response = client.head_object(Bucket=bucket, Key=key)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_upload_and_download_roundtrip(self, s3_client):
        """Conteúdo baixado deve ser idêntico ao conteúdo enviado."""
        client, bucket = s3_client
        key = f"test/{uuid.uuid4()}/data.bin"
        content = b"Dados binarios: \x00\x01\x02\x03\xff\xfe\xfd"

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(content),
            ContentLength=len(content),
        )

        response = client.get_object(Bucket=bucket, Key=key)
        downloaded = response["Body"].read()
        assert downloaded == content

    def test_upload_binary_pdf_simulated(self, s3_client):
        """Upload de dados binários simulando um PDF."""
        client, bucket = s3_client
        key = f"company-test/{uuid.uuid4()}/document.pdf"

        # Simula header PDF + dados binários
        pdf_content = b"%PDF-1.4\n" + b"\x00" * 512

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(pdf_content),
            ContentLength=len(pdf_content),
            ContentType="application/pdf",
        )

        response = client.get_object(Bucket=bucket, Key=key)
        downloaded = response["Body"].read()
        assert downloaded == pdf_content

    def test_upload_large_content(self, s3_client):
        """Upload de conteúdo maior (100KB) deve ser suportado."""
        client, bucket = s3_client
        key = f"test/{uuid.uuid4()}/large.bin"
        content = b"x" * 102_400  # 100KB

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(content),
            ContentLength=len(content),
        )

        response = client.get_object(Bucket=bucket, Key=key)
        downloaded = response["Body"].read()
        assert len(downloaded) == 102_400

    def test_upload_json_metadata(self, s3_client):
        """Upload de JSON (Bronze Layer) deve preservar conteúdo."""
        import json
        client, bucket = s3_client
        key = f"company-test/{uuid.uuid4()}/raw/document.json"
        data = {
            "company_id": "test-company",
            "document_id": str(uuid.uuid4()),
            "chunks": ["chunk1", "chunk2"],
        }
        content = json.dumps(data).encode("utf-8")

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(content),
            ContentLength=len(content),
            ContentType="application/json",
        )

        response = client.get_object(Bucket=bucket, Key=key)
        downloaded = json.loads(response["Body"].read())
        assert downloaded["company_id"] == "test-company"


# ===========================================================================
# TestStorageDelete
# ===========================================================================


class TestStorageDelete:

    def test_delete_existing_file_succeeds(self, s3_client):
        """Deletar arquivo existente deve remover sem erro."""
        client, bucket = s3_client
        key = f"test/{uuid.uuid4()}/to_delete.txt"
        content = b"Delete me"

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=io.BytesIO(content),
            ContentLength=len(content),
        )

        # Verificar que existe
        client.head_object(Bucket=bucket, Key=key)

        # Deletar
        client.delete_object(Bucket=bucket, Key=key)

        # Verificar que não existe mais
        with pytest.raises(client.exceptions.NoSuchKey):
            client.get_object(Bucket=bucket, Key=key)

    def test_delete_nonexistent_file_no_error(self, s3_client):
        """
        Deletar arquivo inexistente não deve levantar erro (idempotente).
        S3 retorna 204 mesmo para objetos que não existem.
        """
        client, bucket = s3_client
        key = f"test/{uuid.uuid4()}/nonexistent.txt"

        # Deve completar sem erro
        response = client.delete_object(Bucket=bucket, Key=key)
        assert response["ResponseMetadata"]["HTTPStatusCode"] in (200, 204)


# ===========================================================================
# TestStorageList
# ===========================================================================


class TestStorageList:

    def test_list_files_by_prefix(self, s3_client):
        """Listar objetos por prefixo deve retornar apenas os objetos daquele prefixo."""
        client, bucket = s3_client
        company_prefix = f"company-{uuid.uuid4().hex[:8]}"

        # Upload de 3 arquivos com o mesmo prefixo
        keys = [f"{company_prefix}/doc{i}.txt" for i in range(3)]
        for key in keys:
            content = f"content-{key}".encode()
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=io.BytesIO(content),
                ContentLength=len(content),
            )

        # Upload de 1 arquivo com prefixo diferente (não deve aparecer)
        other_key = f"other-company/doc.txt"
        other_content = b"other"
        client.put_object(
            Bucket=bucket,
            Key=other_key,
            Body=io.BytesIO(other_content),
            ContentLength=len(other_content),
        )

        # Listar apenas os do nosso prefixo
        response = client.list_objects_v2(Bucket=bucket, Prefix=company_prefix)
        listed_keys = [obj["Key"] for obj in response.get("Contents", [])]

        for key in keys:
            assert key in listed_keys
        assert other_key not in listed_keys

    def test_list_returns_empty_for_nonexistent_prefix(self, s3_client):
        """Listar objetos com prefixo inexistente deve retornar lista vazia."""
        client, bucket = s3_client
        response = client.list_objects_v2(
            Bucket=bucket, Prefix=f"prefix-nonexistent-{uuid.uuid4().hex}"
        )
        contents = response.get("Contents", [])
        assert contents == []

    def test_list_multiple_files_counts_correctly(self, s3_client):
        """Número de objetos listados deve corresponder ao número inserido."""
        client, bucket = s3_client
        prefix = f"count-test-{uuid.uuid4().hex[:8]}"

        # Upload de exatamente 5 arquivos
        for i in range(5):
            key = f"{prefix}/file{i}.txt"
            content = b"test"
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=io.BytesIO(content),
                ContentLength=len(content),
            )

        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        assert len(response.get("Contents", [])) == 5
