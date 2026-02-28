"""
E2E tests for Chat Flow — Testa o ciclo completo de conversas via processo_whatsapp_background.

Dado que o endpoint /api/chat requer o app completo com LangGraph graph
e infraestrutura Supabase real, estes testes testam o fluxo via a
função process_whatsapp_message_background que é o núcleo do processamento.

Cenários:
  - Fluxo normal text → AI response → WhatsApp
  - Billing insuficiente → aviso, sem AI
  - Human mode → salva mensagem, sem AI
  - Múltiplas mensagens combinadas (buffer)

Complementa os testes unitários (test_webhook.py) com um cenário mais
próximo do fluxo real, verificando a interação entre os componentes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# Fixtures locais
# ===========================================================================

_COMPANY_ID = "company-chat-test-123"
_AGENT_ID = "agent-chat-test-456"
_USER_PHONE = "5511888880000"
_CONNECTED_PHONE = "5511999990000"


@pytest.fixture
def chat_payload():
    """Payload WhatsApp padrão para testes de chat."""
    return {
        "connectedPhone": _CONNECTED_PHONE,
        "phone": _USER_PHONE,
        "isGroup": False,
        "fromMe": False,
        "text": {"message": "Qual o horário de funcionamento?"},
    }


@pytest.fixture
def integration_data():
    """Dados de integração simulados para os testes."""
    return {
        "company_id": _COMPANY_ID,
        "agent_id": _AGENT_ID,
    }


@pytest.fixture
def chat_mocks(integration_data, monkeypatch):
    """
    Mock completo para process_whatsapp_message_background:
    - integration_service com integração configurada
    - supabase com respostas simuladas
    - LangChainService com AsyncMock
    - whatsapp_service com send_message
    - billing_service com saldo suficiente
    """
    import app.api.webhook as webhook_mod

    # Integration
    mock_integration = MagicMock()
    mock_integration.get_integration_by_phone.return_value = integration_data
    mock_integration.get_or_create_user.return_value = "user-chat-test"
    monkeypatch.setattr(webhook_mod, "integration_service", mock_integration)

    # Supabase
    mock_table = MagicMock()
    for method in ["select", "eq", "limit", "single", "insert", "update", "is_"]:
        getattr(mock_table, method).return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])
    mock_supabase = MagicMock()
    mock_supabase.client.table.return_value = mock_table
    monkeypatch.setattr(webhook_mod, "supabase", mock_supabase)

    # Conversation helper
    mock_get_conv = AsyncMock(return_value="conv-chat-test")
    monkeypatch.setattr(webhook_mod, "get_or_create_conversation", mock_get_conv)

    # LangChain
    mock_lc_instance = MagicMock()
    mock_lc_instance.process_message = AsyncMock(
        return_value=("Funcionamos de seg a sex, 9h às 18h.", {})
    )
    mock_lc_class = MagicMock(return_value=mock_lc_instance)
    monkeypatch.setattr(webhook_mod, "LangChainService", mock_lc_class)

    # WhatsApp
    mock_whatsapp = MagicMock()
    mock_whatsapp.send_message.return_value = True
    monkeypatch.setattr(webhook_mod, "whatsapp_service", mock_whatsapp)

    return {
        "integration": mock_integration,
        "lc_instance": mock_lc_instance,
        "lc_class": mock_lc_class,
        "whatsapp": mock_whatsapp,
        "table": mock_table,
    }


# ===========================================================================
# TestChatFlowNormal
# ===========================================================================


class TestChatFlowNormal:
    """Fluxo normal: mensagem texto → LLM → resposta WhatsApp."""

    async def test_full_text_chat_flow(self, chat_payload, chat_mocks):
        """Fluxo completo: text → LangChain → send WhatsApp."""
        from app.api.webhook import process_whatsapp_message_background

        with patch("app.services.billing_service.get_billing_service") as mock_billing_factory:
            mock_billing = MagicMock()
            mock_billing.has_sufficient_balance.return_value = True
            mock_billing_factory.return_value = mock_billing

            await process_whatsapp_message_background(chat_payload)

        # LangChain chamado com a mensagem do usuário
        chat_mocks["lc_instance"].process_message.assert_called_once()
        call_kwargs = chat_mocks["lc_instance"].process_message.call_args.kwargs
        assert call_kwargs["user_message"] == "Qual o horário de funcionamento?"
        assert call_kwargs["company_id"] == _COMPANY_ID

        # Resposta enviada via WhatsApp
        chat_mocks["whatsapp"].send_message.assert_called()
        send_kwargs = chat_mocks["whatsapp"].send_message.call_args.kwargs
        assert send_kwargs["to_number"] == _USER_PHONE

    async def test_combined_messages_sent_to_llm(self, chat_payload, chat_mocks):
        """Buffer de múltiplas mensagens → enviadas combinadas ao LLM."""
        from app.api.webhook import process_whatsapp_message_background

        combined = "Mensagem 1. Mensagem 2. Mensagem 3."
        with patch("app.services.billing_service.get_billing_service") as mock_billing_factory:
            mock_billing = MagicMock()
            mock_billing.has_sufficient_balance.return_value = True
            mock_billing_factory.return_value = mock_billing

            await process_whatsapp_message_background(
                chat_payload, combined_message=combined
            )

        call_kwargs = chat_mocks["lc_instance"].process_message.call_args.kwargs
        assert call_kwargs["user_message"] == combined

    async def test_ai_response_content_sent_to_user(self, chat_payload, chat_mocks):
        """Conteúdo da resposta AI deve ser o mesmo enviado via WhatsApp."""
        from app.api.webhook import process_whatsapp_message_background

        expected_response = "Nossa loja abre de segunda a sábado."
        chat_mocks["lc_instance"].process_message = AsyncMock(
            return_value=(expected_response, {})
        )

        with patch("app.services.billing_service.get_billing_service") as mock_billing_factory:
            mock_billing = MagicMock()
            mock_billing.has_sufficient_balance.return_value = True
            mock_billing_factory.return_value = mock_billing

            await process_whatsapp_message_background(chat_payload)

        send_kwargs = chat_mocks["whatsapp"].send_message.call_args.kwargs
        assert send_kwargs["text"] == expected_response


# ===========================================================================
# TestChatFlowBlocked
# ===========================================================================


class TestChatFlowBlocked:
    """Fluxo bloqueado: billing insuficiente ou modo humano."""

    async def test_insufficient_balance_sends_warning_not_ai(self, chat_payload, chat_mocks):
        """Saldo zerado → aviso ao usuário, sem chamar LLM."""
        from app.api.webhook import process_whatsapp_message_background

        with patch("app.services.billing_service.get_billing_service") as mock_billing_factory:
            mock_billing = MagicMock()
            mock_billing.has_sufficient_balance.return_value = False
            mock_billing_factory.return_value = mock_billing

            await process_whatsapp_message_background(chat_payload)

        # LLM NÃO chamado
        chat_mocks["lc_instance"].process_message.assert_not_called()

        # Mensagem de aviso enviada
        chat_mocks["whatsapp"].send_message.assert_called_once()

    async def test_human_mode_skips_llm_completely(self, chat_payload, chat_mocks):
        """Status HUMAN_REQUESTED → sem billing, sem LLM."""
        from app.api.webhook import process_whatsapp_message_background

        # Simula conversa em modo humano
        chat_mocks["table"].execute.return_value = MagicMock(
            data=[{"status": "HUMAN_REQUESTED"}]
        )

        with patch("app.services.billing_service.get_billing_service") as mock_billing_factory:
            await process_whatsapp_message_background(chat_payload)
            mock_billing_factory.assert_not_called()

        chat_mocks["lc_instance"].process_message.assert_not_called()
