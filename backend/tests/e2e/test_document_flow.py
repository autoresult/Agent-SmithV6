"""
E2E tests for Document Flow — Upload, validação e processamento.

Testa o ciclo de vida de documentos via as funções centrais do módulo
app/api/documents.py:

Cenários:
  - Upload com agent_id ausente → HTTP 400
  - Upload com tipo inválido → HTTP 400
  - Upload com arquivo > 10MB → HTTP 400
  - Upload válido → chama document_service e agenda background task
  - Background task com sucesso → ingestion_service.process_document chamado
  - Background task com falha → status "failed" salvo

Estratégia: Similar a test_chat_flow.py — usa httpx.AsyncClient com
ASGITransport para testar o endpoint HTTP completo, mas com os serviços
de infraestrutura (storage, DB, Qdrant) mockados.

Nota técnica: app.api.documents deve ser importado antes de qualquer
patch() call — do contrário pkgutil.resolve_name falha porque
sys.modules["app.api.documents"] ainda não existe.
"""

import io
import pytest
from unittest.mock import MagicMock, patch


# ===========================================================================
# Fixtures locais
# ===========================================================================

_COMPANY_ID = "company-doc-test-123"
_AGENT_ID = "agent-doc-test-456"
_DOCUMENT_ID = "doc-test-uuid-789"


@pytest.fixture(scope="module")
def docs_app():
    """
    FastAPI app mínimo com o router de documentos registrado.
    LLMs, storage e DB são mockados via monkeypatch no módulo.
    """
    # Importar o módulo primeiro — garante que está em sys.modules
    # antes de qualquer patch() call.
    import app.api.documents as docs_mod  # noqa: F401

    from fastapi import FastAPI

    app = FastAPI(title="Test Documents App")

    mock_doc_service = MagicMock()
    mock_doc_service.upload_document.return_value = _DOCUMENT_ID

    mock_qdrant = MagicMock()
    mock_ingestion = MagicMock()
    mock_redis = MagicMock()

    with (
        patch("app.api.documents.get_document_service", return_value=mock_doc_service),
        patch("app.api.documents.get_qdrant_service", return_value=mock_qdrant),
        patch("app.api.documents.get_ingestion_service", return_value=mock_ingestion),
        patch("app.api.documents.get_redis_client", return_value=mock_redis),
        patch("app.api.documents.get_benchmark_service", return_value=MagicMock()),
        # Desabilita o rate limiter no decorator
        patch("app.core.rate_limit.limiter.limit", side_effect=lambda *a, **kw: lambda f: f),
    ):
        from app.api.documents import router as docs_router
        app.include_router(docs_router, prefix="/api")

    return app, mock_doc_service, mock_ingestion


@pytest.fixture
async def docs_client(docs_app):
    """httpx.AsyncClient para o docs_app, com reset de mocks entre testes."""
    import httpx
    from httpx import ASGITransport

    app, mock_doc_service, mock_ingestion = docs_app

    # Reset mocks entre testes
    mock_doc_service.reset_mock()
    mock_doc_service.upload_document.return_value = _DOCUMENT_ID
    mock_ingestion.reset_mock()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, mock_doc_service, mock_ingestion


# ===========================================================================
# TestDocumentUploadValidation
# ===========================================================================


@pytest.mark.e2e
class TestDocumentUploadValidation:
    """Valida regras de negócio do endpoint POST /documents/upload."""

    async def test_missing_agent_id_returns_400(self, docs_client):
        """Sem agent_id (vazio) → 400 Bad Request."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("doc.pdf", io.BytesIO(b"PDF"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": "", "strategy": "semantic"},
        )
        assert response.status_code == 400
        assert "agent_id" in response.json()["detail"].lower()

    async def test_unsupported_file_type_returns_400(self, docs_client):
        """Arquivo .exe → 400 Bad Request."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID, "strategy": "semantic"},
        )
        assert response.status_code == 400
        assert "suportado" in response.json()["detail"].lower()

    async def test_file_too_large_returns_400(self, docs_client):
        """Arquivo > 10MB → 400 Bad Request."""
        client, _, _ = docs_client
        big_content = b"X" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        assert response.status_code == 400
        assert "grande" in response.json()["detail"].lower()

    async def test_valid_txt_file_accepted(self, docs_client):
        """Arquivo .txt → aceito (200)."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", io.BytesIO(b"Texto simples"), "text/plain")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID, "strategy": "semantic"},
        )
        assert response.status_code == 200

    async def test_valid_csv_file_accepted(self, docs_client):
        """Arquivo .csv → aceito."""
        client, _, _ = docs_client
        csv_content = b"id,nome,valor\n1,Produto A,10.00"
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("catalog.csv", io.BytesIO(csv_content), "text/csv")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID, "strategy": "semantic"},
        )
        assert response.status_code == 200


# ===========================================================================
# TestDocumentUploadSuccess
# ===========================================================================


@pytest.mark.e2e
class TestDocumentUploadSuccess:
    """Verifica o que acontece em um upload bem-sucedido."""

    async def test_upload_returns_document_id(self, docs_client):
        """Upload válido → resposta contém document_id."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("manual.pdf", io.BytesIO(b"PDF data"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["document_id"] == _DOCUMENT_ID

    async def test_upload_returns_agent_id(self, docs_client):
        """Resposta deve incluir o agent_id passado no form."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("guide.pdf", io.BytesIO(b"PDF data"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        body = response.json()
        assert body["agent_id"] == _AGENT_ID

    async def test_upload_calls_document_service(self, docs_client):
        """document_service.upload_document deve ser chamado com os parâmetros corretos."""
        client, mock_doc_service, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("faq.pdf", io.BytesIO(b"FAQ"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        assert response.status_code == 200
        mock_doc_service.upload_document.assert_called_once()
        call_kwargs = mock_doc_service.upload_document.call_args.kwargs
        assert call_kwargs["company_id"] == _COMPANY_ID
        assert call_kwargs["agent_id"] == _AGENT_ID
        assert call_kwargs["filename"] == "faq.pdf"

    async def test_upload_status_is_processing(self, docs_client):
        """Status inicial após upload deve ser 'processing'."""
        client, _, _ = docs_client
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("policy.pdf", io.BytesIO(b"Policy"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        body = response.json()
        assert body["status"] == "processing"

    async def test_upload_storage_failure_returns_500(self, docs_client):
        """Se document_service retorna None → 500 Internal Server Error."""
        client, mock_doc_service, _ = docs_client
        mock_doc_service.upload_document.return_value = None

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("fail.pdf", io.BytesIO(b"PDF"), "application/pdf")},
            data={"company_id": _COMPANY_ID, "agent_id": _AGENT_ID},
        )
        assert response.status_code == 500


# ===========================================================================
# TestDocumentProcessingTask
# ===========================================================================


@pytest.mark.e2e
class TestDocumentProcessingTask:
    """Testa a background task de processamento de documentos."""

    def test_process_document_task_calls_ingestion(self):
        """Background task com sucesso → ingestion_service.process_document chamado."""
        import app.api.documents as docs_mod  # garante import antes do patch

        mock_ingestion = MagicMock()
        mock_ingestion.process_document.return_value = True

        with patch.object(docs_mod, "get_ingestion_service", return_value=mock_ingestion):
            from app.api.documents import process_document_task

            process_document_task(
                document_id=_DOCUMENT_ID,
                company_id=_COMPANY_ID,
                strategy="semantic",
                agent_id=_AGENT_ID,
            )

        mock_ingestion.process_document.assert_called_once_with(
            document_id=_DOCUMENT_ID,
            company_id=_COMPANY_ID,
            strategy="semantic",
            agent_id=_AGENT_ID,
        )

    def test_process_document_task_without_agent_id_does_not_call_ingestion(self):
        """Background task sem agent_id → não chama ingestion, salva status 'failed'."""
        import app.api.documents as docs_mod

        mock_ingestion = MagicMock()
        mock_doc_service = MagicMock()

        with (
            patch.object(docs_mod, "get_ingestion_service", return_value=mock_ingestion),
            patch.object(docs_mod, "get_document_service", return_value=mock_doc_service),
        ):
            from app.api.documents import process_document_task

            # Não deve propagar a exceção — a task captura e salva status "failed"
            process_document_task(
                document_id=_DOCUMENT_ID,
                company_id=_COMPANY_ID,
                strategy="semantic",
                agent_id=None,  # Inválido
            )

        # Ingestion NÃO chamado
        mock_ingestion.process_document.assert_not_called()

        # Status "failed" salvo
        mock_doc_service.update_document_status.assert_called_once()
        call_kwargs = mock_doc_service.update_document_status.call_args.kwargs
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["document_id"] == _DOCUMENT_ID

    def test_process_document_task_ingestion_failure_saves_status(self):
        """Se ingestion_service.process_document levanta exceção → status 'failed' salvo."""
        import app.api.documents as docs_mod

        mock_ingestion = MagicMock()
        mock_ingestion.process_document.side_effect = RuntimeError("Qdrant unavailable")
        mock_doc_service = MagicMock()

        with (
            patch.object(docs_mod, "get_ingestion_service", return_value=mock_ingestion),
            patch.object(docs_mod, "get_document_service", return_value=mock_doc_service),
        ):
            from app.api.documents import process_document_task

            process_document_task(
                document_id=_DOCUMENT_ID,
                company_id=_COMPANY_ID,
                strategy="semantic",
                agent_id=_AGENT_ID,
            )

        # Status "failed" salvo com mensagem de erro
        mock_doc_service.update_document_status.assert_called_once()
        call_kwargs = mock_doc_service.update_document_status.call_args.kwargs
        assert call_kwargs["status"] == "failed"
        assert "Qdrant" in call_kwargs.get("error_message", "")
