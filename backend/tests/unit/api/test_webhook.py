"""
Unit tests for app/api/webhook.py — Z-API Webhook Business Logic.

Scope:
  1. ZAPIWebhookPayload — Pydantic model validation and field defaults
  2. process_whatsapp_message_background — Core async processing logic:
       - No integration found → returns early
       - HUMAN_REQUESTED mode → saves message, skips billing + AI
       - Insufficient balance → sends warning, skips AI
       - Normal text flow → calls LangChainService, sends AI response
       - combined_message parameter → overrides payload text
       - Payload without content → returns early

Architecture note:
  The z_api_webhook route endpoint uses @limiter.limit() (slowapi),
  which under the unit test mock setup wraps the function in a MagicMock.
  Route-level tests (isGroup/fromMe filters, text buffering, media dispatch)
  are covered in tests/e2e/test_webhook_flow.py via the full FastAPI TestClient.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class TestZAPIWebhookPayloadModel:
    """Valida modelo ZAPIWebhookPayload — fields, defaults, nested parsing."""

    def test_default_isGroup_false(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(connectedPhone="5511999990000", phone="5511888880000")
        assert p.isGroup is False

    def test_default_fromMe_false(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(connectedPhone="5511999990000", phone="5511888880000")
        assert p.fromMe is False

    def test_optional_fields_default_none(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(connectedPhone="5511999990000", phone="5511888880000")
        assert p.text is None
        assert p.audio is None
        assert p.image is None
        assert p.messageId is None
        assert p.senderName is None

    def test_text_payload_parsed(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            text={"message": "Olá, mundo!"},
        )
        assert p.text is not None
        assert p.text.message == "Olá, mundo!"

    def test_audio_payload_parsed(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            audio={"audioUrl": "https://example.com/audio.ogg"},
        )
        assert p.audio is not None
        assert p.audio.audioUrl == "https://example.com/audio.ogg"

    def test_image_payload_with_caption(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            image={"imageUrl": "https://example.com/photo.jpg", "caption": "Foto importante"},
        )
        assert p.image is not None
        assert p.image.imageUrl == "https://example.com/photo.jpg"
        assert p.image.caption == "Foto importante"

    def test_isGroup_true_preserved(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            isGroup=True,
        )
        assert p.isGroup is True

    def test_fromMe_true_preserved(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            fromMe=True,
        )
        assert p.fromMe is True

    def test_sender_name_stored(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            senderName="João Silva",
        )
        assert p.senderName == "João Silva"

    def test_image_audio_url_optional(self):
        from app.api.webhook import ZAPIWebhookPayload
        p = ZAPIWebhookPayload(
            connectedPhone="5511999990000",
            phone="5511888880000",
            audio={"audioUrl": None},
        )
        assert p.audio is not None
        assert p.audio.audioUrl is None


# ===========================================================================
# FIXTURES — process_whatsapp_message_background
# ===========================================================================

# Payload mínimo com mensagem de texto
_BASE_PAYLOAD = {
    "connectedPhone": "5511999990000",
    "phone": "5511888880000",
    "isGroup": False,
    "fromMe": False,
    "text": {"message": "Olá, preciso de ajuda."},
}


@pytest.fixture
def mock_webhook_deps(monkeypatch):
    """
    Patcha todos os singletons de process_whatsapp_message_background:
      - integration_service, supabase, whatsapp_service → monkeypatch no módulo
      - get_or_create_conversation → AsyncMock (evita chain de DB complexa)
      - LangChainService → MagicMock com process_message AsyncMock

    A supabase mock retorna status_response (data=[]) por padrão,
    que significa: sem conversa em HUMAN_REQUESTED mode.
    """
    import app.api.webhook as webhook_mod

    # ── Integration Service ──────────────────────────────────────────────
    mock_integration = MagicMock()
    mock_integration.get_integration_by_phone.return_value = {
        "company_id": "company-123",
        "agent_id": "agent-456",
    }
    mock_integration.get_or_create_user.return_value = "user-789"
    monkeypatch.setattr(webhook_mod, "integration_service", mock_integration)

    # ── Supabase (human mode check + inserts de mensagens) ───────────────
    mock_table = MagicMock()
    for method in ["select", "eq", "limit", "single", "insert", "update", "is_", "order"]:
        getattr(mock_table, method).return_value = mock_table
    status_response = MagicMock()
    status_response.data = []  # Default: sem conversa → não é modo humano
    mock_table.execute.return_value = status_response

    mock_supabase = MagicMock()
    mock_supabase.client.table.return_value = mock_table
    monkeypatch.setattr(webhook_mod, "supabase", mock_supabase)

    # ── get_or_create_conversation → AsyncMock direto ───────────────────
    # Evita complexidade de mockar toda a chain de DB para criação de conversa
    mock_get_conv = AsyncMock(return_value="conv-123")
    monkeypatch.setattr(webhook_mod, "get_or_create_conversation", mock_get_conv)

    # ── LangChainService ─────────────────────────────────────────────────
    mock_lc_instance = MagicMock()
    mock_lc_instance.process_message = AsyncMock(return_value=("Resposta da IA.", {}))
    mock_lc_class = MagicMock(return_value=mock_lc_instance)
    monkeypatch.setattr(webhook_mod, "LangChainService", mock_lc_class)

    # ── WhatsApp Service ─────────────────────────────────────────────────
    mock_whatsapp = MagicMock()
    mock_whatsapp.send_message.return_value = True
    monkeypatch.setattr(webhook_mod, "whatsapp_service", mock_whatsapp)

    return {
        "integration": mock_integration,
        "supabase_table": mock_table,
        "status_response": status_response,
        "get_conv": mock_get_conv,
        "lc_instance": mock_lc_instance,
        "lc_class": mock_lc_class,
        "whatsapp": mock_whatsapp,
    }


# ===========================================================================
# PROCESS WHATSAPP MESSAGE BACKGROUND
# ===========================================================================


class TestProcessWhatsappBackground:
    """Testa a task de background principal do webhook Z-API."""

    async def test_no_integration_returns_early(self, mock_webhook_deps):
        """Integração não encontrada → retorna sem processar nada."""
        from app.api.webhook import process_whatsapp_message_background

        mock_webhook_deps["integration"].get_integration_by_phone.return_value = None

        result = await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        assert result is None
        mock_webhook_deps["whatsapp"].send_message.assert_not_called()
        mock_webhook_deps["get_conv"].assert_not_called()
        mock_webhook_deps["lc_instance"].process_message.assert_not_called()

    async def test_human_mode_skips_billing_and_ai(self, mock_webhook_deps):
        """Status HUMAN_REQUESTED → salva mensagem, pula billing + IA."""
        from app.api.webhook import process_whatsapp_message_background

        # Simula conversa com status de modo humano
        mock_webhook_deps["status_response"].data = [{"status": "HUMAN_REQUESTED"}]

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

            # Billing NÃO deve ser consultado em modo humano
            mock_get_billing.assert_not_called()

        # LangChain NÃO deve ser invocado
        mock_webhook_deps["lc_instance"].process_message.assert_not_called()

    async def test_human_mode_conversation_is_created(self, mock_webhook_deps):
        """Em modo humano, a conversa deve ser criada/obtida antes de parar."""
        from app.api.webhook import process_whatsapp_message_background

        mock_webhook_deps["status_response"].data = [{"status": "HUMAN_REQUESTED"}]

        await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        # get_or_create_conversation é chamado mesmo em modo humano
        mock_webhook_deps["get_conv"].assert_called_once()

    async def test_billing_insufficient_sends_warning(self, mock_webhook_deps):
        """Saldo insuficiente → envia aviso ao usuário, sem chamar LLM."""
        from app.api.webhook import process_whatsapp_message_background

        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = False

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        # Saldo verificado com company_id correto
        mock_billing_service.has_sufficient_balance.assert_called_once_with("company-123")

        # Mensagem de aviso enviada ao usuário
        mock_webhook_deps["whatsapp"].send_message.assert_called_once()
        call_kwargs = mock_webhook_deps["whatsapp"].send_message.call_args.kwargs
        assert call_kwargs["to_number"] == "5511888880000"
        warning_text = call_kwargs["text"].lower()
        assert "indispon" in warning_text or "suporte" in warning_text

        # LangChain NÃO chamado
        mock_webhook_deps["lc_instance"].process_message.assert_not_called()

    async def test_text_message_invokes_langchain(self, mock_webhook_deps):
        """Texto normal com saldo ok → LangChainService instanciado e chamado."""
        from app.api.webhook import process_whatsapp_message_background

        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = True

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        # LangChain instanciado e process_message chamado
        mock_webhook_deps["lc_class"].assert_called_once()
        mock_webhook_deps["lc_instance"].process_message.assert_called_once()

        call_kwargs = mock_webhook_deps["lc_instance"].process_message.call_args.kwargs
        assert call_kwargs["user_message"] == "Olá, preciso de ajuda."
        assert call_kwargs["company_id"] == "company-123"
        assert call_kwargs["channel"] == "whatsapp"

    async def test_ai_response_sent_via_whatsapp(self, mock_webhook_deps):
        """Após resposta da IA → enviada via whatsapp_service.send_message."""
        from app.api.webhook import process_whatsapp_message_background

        ai_text = "Posso ajudar com isso! Aqui está a resposta."
        mock_webhook_deps["lc_instance"].process_message = AsyncMock(
            return_value=(ai_text, {})
        )

        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = True

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        mock_webhook_deps["whatsapp"].send_message.assert_called()
        call_kwargs = mock_webhook_deps["whatsapp"].send_message.call_args.kwargs
        assert call_kwargs["to_number"] == "5511888880000"
        assert call_kwargs["text"] == ai_text

    async def test_combined_message_used_as_user_input(self, mock_webhook_deps):
        """combined_message param substitui o texto do payload original."""
        from app.api.webhook import process_whatsapp_message_background

        combined = "Mensagem 1. Mensagem 2. Mensagem 3."
        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = True

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(
                _BASE_PAYLOAD.copy(), combined_message=combined
            )

        call_kwargs = mock_webhook_deps["lc_instance"].process_message.call_args.kwargs
        assert call_kwargs["user_message"] == combined

    async def test_no_content_payload_returns_early(self, mock_webhook_deps):
        """Payload sem text/audio/image → retorna antes de chamar IA."""
        from app.api.webhook import process_whatsapp_message_background

        empty_payload = {
            "connectedPhone": "5511999990000",
            "phone": "5511888880000",
            "isGroup": False,
            "fromMe": False,
            # Sem text, audio ou image
        }

        await process_whatsapp_message_background(empty_payload)

        mock_webhook_deps["lc_instance"].process_message.assert_not_called()
        mock_webhook_deps["whatsapp"].send_message.assert_not_called()

    async def test_session_id_includes_phone_and_company(self, mock_webhook_deps):
        """session_id gerado segue formato: whatsapp:{phone}:{company_id}:{agent_id}."""
        from app.api.webhook import process_whatsapp_message_background

        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = True

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        call_kwargs = mock_webhook_deps["lc_instance"].process_message.call_args.kwargs
        session_id = call_kwargs["session_id"]
        assert session_id.startswith("whatsapp:")
        assert "5511888880000" in session_id
        assert "company-123" in session_id

    async def test_agent_id_passed_to_langchain(self, mock_webhook_deps):
        """agent_id da integração é passado corretamente ao LangChainService."""
        from app.api.webhook import process_whatsapp_message_background

        mock_billing_service = MagicMock()
        mock_billing_service.has_sufficient_balance.return_value = True

        with patch("app.services.billing_service.get_billing_service") as mock_get_billing:
            mock_get_billing.return_value = mock_billing_service
            await process_whatsapp_message_background(_BASE_PAYLOAD.copy())

        call_kwargs = mock_webhook_deps["lc_instance"].process_message.call_args.kwargs
        assert call_kwargs.get("agent_id") == "agent-456"
