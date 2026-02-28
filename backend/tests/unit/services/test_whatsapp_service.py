"""
Unit tests for WhatsappService — Z-API message sending.
"""

import requests
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def whatsapp_service():
    """WhatsappService instanciado sem side effects."""
    from app.services.whatsapp_service import WhatsappService
    return WhatsappService()


@pytest.fixture
def integration():
    """Configuração de integração Z-API mock."""
    return {
        "token": "test-token-123",
        "instance_id": "inst-456",
        "base_url": "https://api.z-api.io/instances",
    }


# ═══════════════════════════════════════════════════════════════════════════
# SEND MESSAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestSendMessage:

    @patch.object(requests, "post")
    def test_sends_text_message_successfully(self, mock_post, whatsapp_service, integration):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"zapiMessageId": "msg-1"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = whatsapp_service.send_message("5511999990001", "Olá!", integration)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "send-text" in call_args[0][0]  # URL contains send-text

    @patch.object(requests, "post")
    def test_raises_on_http_error(self, mock_post, whatsapp_service, integration):
        """send_message re-raises exceptions (doesn't return False)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with pytest.raises(Exception, match="Failed to send WhatsApp"):
            whatsapp_service.send_message("5511999990001", "Test", integration)

    @patch.object(requests, "post")
    def test_raises_on_network_error(self, mock_post, whatsapp_service, integration):
        mock_post.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        with pytest.raises(Exception, match="Failed to send WhatsApp"):
            whatsapp_service.send_message("5511999990001", "Test", integration)

    def test_raises_when_missing_integration_config(self, whatsapp_service):
        """Deve levantar ValueError sem instance_id ou token."""
        bad_integration = {"base_url": "https://api.z-api.io"}

        with pytest.raises(Exception, match="Missing instance_id"):
            whatsapp_service.send_message("5511999990001", "Test", bad_integration)


# ═══════════════════════════════════════════════════════════════════════════
# SEND AUDIO
# ═══════════════════════════════════════════════════════════════════════════


class TestSendAudio:

    @patch.object(requests, "post")
    def test_sends_audio_successfully(self, mock_post, whatsapp_service, integration):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = whatsapp_service.send_audio(
            "5511999990001", "https://storage.example.com/audio.ogg", integration
        )

        assert result is True

    @patch.object(requests, "post")
    def test_returns_false_on_error(self, mock_post, whatsapp_service, integration):
        mock_post.side_effect = Exception("timeout")

        result = whatsapp_service.send_audio("5511999990001", "https://example.com/a.ogg", integration)

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# SEND IMAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestSendImage:

    @patch.object(requests, "post")
    def test_sends_image_with_caption(self, mock_post, whatsapp_service, integration):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = whatsapp_service.send_image(
            "5511999990001",
            "https://storage.example.com/photo.jpg",
            "Foto do produto",
            integration,
        )

        assert result is True

    @patch.object(requests, "post")
    def test_returns_false_on_error(self, mock_post, whatsapp_service, integration):
        mock_post.side_effect = Exception("connection reset")

        result = whatsapp_service.send_image(
            "5511999990001", "https://example.com/img.jpg", "caption", integration
        )

        assert result is False
