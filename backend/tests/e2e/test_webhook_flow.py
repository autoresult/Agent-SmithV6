"""
E2E tests for Z-API Webhook Flow — HTTP routing e filtros.

Testa o fluxo completo via HTTP:
  POST /api/v1/webhook/z-api → verificação de filtros → buffering/dispatch

Aqui testamos o que não é possível nos testes unitários:
  - isGroup=True → endpoint retorna {status: "ignored"}
  - fromMe=True → endpoint retorna {status: "ignored"}
  - Sem conteúdo → endpoint retorna {status: "ignored"}
  - Texto → buffered
  - Áudio/Imagem → dispatch para background task

Nota: LLMs e serviços externos são mockados.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# Helpers
# ===========================================================================

def _payload(
    phone="5511888880000",
    connected_phone="5511999990000",
    is_group=False,
    from_me=False,
    text=None,
    audio=None,
    image=None,
):
    """Constrói um payload Z-API para testes."""
    data = {
        "connectedPhone": connected_phone,
        "phone": phone,
        "isGroup": is_group,
        "fromMe": from_me,
    }
    if text:
        data["text"] = {"message": text}
    if audio:
        data["audio"] = {"audioUrl": audio}
    if image:
        data["image"] = {"imageUrl": image, "caption": None}
    return data


# ===========================================================================
# TestZApiWebhookFilters
# ===========================================================================


@pytest.mark.e2e
class TestZApiWebhookFilters:
    """Testa filtros de mensagens indesejadas no endpoint."""

    async def test_skips_group_messages(self, e2e_client):
        """isGroup=True → retorna {status: ignored} imediatamente."""
        payload = _payload(is_group=True, text="Mensagem de grupo")
        response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ignored"

    async def test_skips_fromme_messages(self, e2e_client):
        """fromMe=True → retorna {status: ignored} imediatamente."""
        payload = _payload(from_me=True, text="Mensagem enviada por mim")
        response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ignored"

    async def test_skips_no_content_messages(self, e2e_client):
        """Payload sem text/audio/image → retorna {status: ignored}."""
        payload = _payload()  # Sem text, audio, image
        response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ignored"

    async def test_invalid_payload_returns_ignored(self, e2e_client):
        """Payload com campos obrigatórios faltando → retorna {status: ignored}."""
        invalid = {"phone": "5511888880000"}  # Faltando connectedPhone
        response = await e2e_client.post("/api/v1/webhook/z-api", json=invalid)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ignored"


# ===========================================================================
# TestZApiWebhookTextFlow
# ===========================================================================


@pytest.mark.e2e
class TestZApiWebhookTextFlow:
    """Testa fluxo de mensagens de texto (buffer)."""

    async def test_text_message_returns_buffered(self, e2e_client):
        """Texto → chama message_buffer_service.add_message, retorna {status: buffered}."""
        payload = _payload(text="Quero saber sobre os produtos disponíveis")

        with patch("app.api.webhook.message_buffer_service") as mock_buffer:
            response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "buffered"

    async def test_text_message_returns_phone_in_body(self, e2e_client):
        """Resposta buffered deve incluir o phone no body."""
        payload = _payload(phone="5511777770000", text="Olá!")

        with patch("app.api.webhook.message_buffer_service"):
            response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        body = response.json()
        assert body.get("phone") == "5511777770000"


# ===========================================================================
# TestZApiWebhookMediaFlow
# ===========================================================================


@pytest.mark.e2e
class TestZApiWebhookMediaFlow:
    """Testa fluxo de mídia (audio/imagem) → background task."""

    async def test_audio_dispatches_background_task(self, e2e_client):
        """Áudio → dispatch para background task, retorna {status: received, type: media}."""
        payload = _payload(audio="https://example.com/audio.ogg")

        response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "received"
        assert body.get("type") == "media"

    async def test_image_dispatches_background_task(self, e2e_client):
        """Imagem → dispatch para background task, retorna {status: received, type: media}."""
        payload = _payload(image="https://example.com/photo.jpg")

        response = await e2e_client.post("/api/v1/webhook/z-api", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "received"
        assert body.get("type") == "media"


# ===========================================================================
# TestWebhookHealth
# ===========================================================================


@pytest.mark.e2e
class TestWebhookHealth:
    """Testa endpoint de health check do webhook."""

    async def test_health_endpoint_returns_200(self, e2e_client):
        """GET /api/v1/webhook/z-api/health → 200 OK."""
        response = await e2e_client.get("/api/v1/webhook/z-api/health")
        assert response.status_code == 200

    async def test_health_endpoint_returns_healthy_status(self, e2e_client):
        """Health check deve retornar status=healthy."""
        response = await e2e_client.get("/api/v1/webhook/z-api/health")
        body = response.json()
        assert body.get("status") == "healthy"
        assert body.get("webhook") == "z-api"
