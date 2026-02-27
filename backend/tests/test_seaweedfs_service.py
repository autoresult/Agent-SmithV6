"""
Testes unitários do SeaweedFSService.

Usa moto[s3] para mockar a API S3 inteiramente — sem Docker, sem SeaweedFS real.
Todos os testes rodam em memória.
"""

import json
from io import BytesIO

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.services.storage.seaweedfs_service import SeaweedFSService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BUCKET = "documents"
REGION = "us-east-1"
FAKE_ENDPOINT = "http://localhost:8333"


@pytest.fixture
def aws_credentials(monkeypatch):
    """Garante que boto3 use credenciais falsas dentro do mock."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)


@pytest.fixture
def seaweedfs_settings(monkeypatch):
    """Injeta configurações do SeaweedFS apontando para o mock."""
    monkeypatch.setattr("app.services.storage.seaweedfs_service.settings.SEAWEEDFS_ENDPOINT", "localhost:8333")
    monkeypatch.setattr("app.services.storage.seaweedfs_service.settings.SEAWEEDFS_ACCESS_KEY", "testing")
    monkeypatch.setattr("app.services.storage.seaweedfs_service.settings.SEAWEEDFS_SECRET_KEY", "testing")
    monkeypatch.setattr("app.services.storage.seaweedfs_service.settings.SEAWEEDFS_SECURE", False)
    monkeypatch.setattr("app.services.storage.seaweedfs_service.settings.SEAWEEDFS_BUCKET", BUCKET)


@pytest.fixture
def svc(aws_credentials, seaweedfs_settings):
    """Instância de SeaweedFSService com S3 inteiramente mockado pelo moto."""
    with mock_aws():
        # Cria o bucket no mock para simular _ensure_bucket_exists
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET)

        service = SeaweedFSService.__new__(SeaweedFSService)
        service.bucket_name = BUCKET
        service.client = boto3.client(
            "s3",
            region_name=REGION,
        )
        yield service


# ---------------------------------------------------------------------------
# Testes de inicialização
# ---------------------------------------------------------------------------

class TestBucketInit:
    def test_bucket_created_when_not_exists(self, aws_credentials, seaweedfs_settings):
        with mock_aws():
            service = SeaweedFSService.__new__(SeaweedFSService)
            service.bucket_name = BUCKET
            service.client = boto3.client("s3", region_name=REGION)
            service._ensure_bucket_exists()

            s3 = boto3.client("s3", region_name=REGION)
            buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
            assert BUCKET in buckets

    def test_no_error_when_bucket_already_exists(self, svc):
        # Segunda chamada não deve lançar exceção
        svc._ensure_bucket_exists()


# ---------------------------------------------------------------------------
# Testes de upload_file
# ---------------------------------------------------------------------------

class TestUploadFile:
    def test_returns_correct_object_name(self, svc):
        data = BytesIO(b"conteudo do pdf")
        result = svc.upload_file(data, "empresa1", "doc-abc", "contrato.pdf")
        assert result == "empresa1/doc-abc/contrato.pdf"

    def test_file_stored_in_bucket(self, svc):
        data = BytesIO(b"hello world")
        svc.upload_file(data, "empresa1", "doc-xyz", "arquivo.txt")
        response = svc.client.get_object(Bucket=BUCKET, Key="empresa1/doc-xyz/arquivo.txt")
        assert response["Body"].read() == b"hello world"

    def test_accepts_non_bytesio_file_like(self, svc):
        import io
        data = io.BufferedReader(io.BytesIO(b"conteudo binario"))
        result = svc.upload_file(data, "emp", "doc", "file.bin")
        assert result == "emp/doc/file.bin"


# ---------------------------------------------------------------------------
# Testes de upload_object
# ---------------------------------------------------------------------------

class TestUploadObject:
    def test_stores_raw_json(self, svc):
        payload = {"text_content": "texto extraído", "pages": []}
        raw = json.dumps(payload).encode("utf-8")
        data = BytesIO(raw)
        svc.upload_object("empresa1/raw/doc-abc.json", data, len(raw), "application/json")

        response = svc.client.get_object(Bucket=BUCKET, Key="empresa1/raw/doc-abc.json")
        stored = json.loads(response["Body"].read())
        assert stored["text_content"] == "texto extraído"

    def test_content_type_preserved(self, svc):
        data = BytesIO(b"dados")
        svc.upload_object("path/obj.bin", data, 5, "application/octet-stream")
        meta = svc.client.head_object(Bucket=BUCKET, Key="path/obj.bin")
        assert meta["ContentType"] == "application/octet-stream"


# ---------------------------------------------------------------------------
# Testes de download_file
# ---------------------------------------------------------------------------

class TestDownloadFile:
    def test_returns_correct_content(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp/doc/file.txt", Body=b"conteudo")
        result = svc.download_file("emp/doc/file.txt")
        assert isinstance(result, BytesIO)
        assert result.read() == b"conteudo"

    def test_raises_on_missing_object(self, svc):
        with pytest.raises(ClientError):
            svc.download_file("nao/existe/arquivo.txt")


# ---------------------------------------------------------------------------
# Testes de delete_file
# ---------------------------------------------------------------------------

class TestDeleteFile:
    def test_delete_existing_file_returns_true(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp/doc/del.txt", Body=b"x")
        result = svc.delete_file("emp/doc/del.txt")
        assert result is True

    def test_file_no_longer_accessible_after_delete(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp/doc/del.txt", Body=b"x")
        svc.delete_file("emp/doc/del.txt")
        with pytest.raises(ClientError):
            svc.client.get_object(Bucket=BUCKET, Key="emp/doc/del.txt")


# ---------------------------------------------------------------------------
# Testes de delete_folder
# ---------------------------------------------------------------------------

class TestDeleteFolder:
    def test_removes_all_objects_with_prefix(self, svc):
        keys = [
            "emp1/docA/original.pdf",
            "emp1/docA/thumbnail.png",
        ]
        for k in keys:
            svc.client.put_object(Bucket=BUCKET, Key=k, Body=b"data")

        result = svc.delete_folder("emp1", "docA")
        assert result is True

        remaining = svc.client.list_objects_v2(Bucket=BUCKET, Prefix="emp1/docA/")
        assert remaining.get("KeyCount", 0) == 0

    def test_does_not_remove_other_documents(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp1/docA/file.pdf", Body=b"a")
        svc.client.put_object(Bucket=BUCKET, Key="emp1/docB/file.pdf", Body=b"b")

        svc.delete_folder("emp1", "docA")

        response = svc.client.get_object(Bucket=BUCKET, Key="emp1/docB/file.pdf")
        assert response["Body"].read() == b"b"

    def test_returns_true_on_empty_prefix(self, svc):
        result = svc.delete_folder("emp-vazia", "doc-inexistente")
        assert result is True


# ---------------------------------------------------------------------------
# Testes de get_file_url
# ---------------------------------------------------------------------------

class TestGetFileUrl:
    def test_returns_string_url(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp/doc/file.pdf", Body=b"pdf")
        url = svc.get_file_url("emp/doc/file.pdf", expires=300)
        assert isinstance(url, str)
        assert "file.pdf" in url

    def test_url_contains_bucket_and_key(self, svc):
        svc.client.put_object(Bucket=BUCKET, Key="emp/doc/report.pdf", Body=b"data")
        url = svc.get_file_url("emp/doc/report.pdf")
        assert "report.pdf" in url
