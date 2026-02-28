"""
Unit tests for MessageBufferService — WhatsApp message debounce logic.

Testa debounce, max_wait, buffer creation/append, atomic get+clear, e combine.
Redis é mockado via unit/conftest.py fixtures.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.message_buffer_service import MessageBufferService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def buffer_service(mock_redis_client):
    """MessageBufferService com Redis mockado."""
    svc = MessageBufferService.__new__(MessageBufferService)
    svc.redis = mock_redis_client
    return svc


@pytest.fixture
def sample_payload():
    return {
        "phone": "5511999990000",
        "message": "Olá!",
        "integration": {"type": "whatsapp", "instance": "test"},
    }


# ═══════════════════════════════════════════════════════════════════════════
# KEY GENERATION
# ═══════════════════════════════════════════════════════════════════════════


class TestKeyGeneration:

    def test_generates_correct_redis_key(self, buffer_service):
        key = buffer_service._get_key("5511999990000")
        assert key == "whatsapp_buffer:5511999990000"

    def test_different_phones_different_keys(self, buffer_service):
        k1 = buffer_service._get_key("5511999990001")
        k2 = buffer_service._get_key("5511999990002")
        assert k1 != k2


# ═══════════════════════════════════════════════════════════════════════════
# ADD MESSAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestAddMessage:

    def test_first_message_creates_buffer(self, buffer_service, mock_redis_client):
        """Primeiro msg retorna True (is_first) e cria novo buffer."""
        mock_redis_client.get.return_value = None  # No existing buffer

        is_first = buffer_service.add_message(
            phone="5511999990000",
            message="Olá!",
            company_id="company-1",
            user_id="user-1",
            integration={"type": "whatsapp"},
            payload={"raw": "data"},
        )

        assert is_first is True
        mock_redis_client.setex.assert_called_once()
        # Verifica que o buffer foi salvo com TTL
        call_args = mock_redis_client.setex.call_args
        saved_data = json.loads(call_args[0][2])
        assert saved_data["messages"] == ["Olá!"]
        assert saved_data["company_id"] == "company-1"

    def test_subsequent_message_appends(self, buffer_service, mock_redis_client):
        """Segunda msg retorna False e anexa ao buffer existente."""
        existing_buffer = {
            "messages": ["Olá!"],
            "first_at": datetime.now().isoformat(),
            "last_at": datetime.now().isoformat(),
            "company_id": "company-1",
            "user_id": "user-1",
            "integration": {"type": "whatsapp"},
            "payload": {"raw": "old"},
        }
        mock_redis_client.get.return_value = json.dumps(existing_buffer)

        is_first = buffer_service.add_message(
            phone="5511999990000",
            message="Tudo bem?",
            company_id="company-1",
            user_id="user-1",
            integration={"type": "whatsapp"},
            payload={"raw": "new"},
        )

        assert is_first is False
        saved_data = json.loads(mock_redis_client.setex.call_args[0][2])
        assert saved_data["messages"] == ["Olá!", "Tudo bem?"]
        assert saved_data["payload"] == {"raw": "new"}  # Updated to latest


# ═══════════════════════════════════════════════════════════════════════════
# SHOULD PROCESS
# ═══════════════════════════════════════════════════════════════════════════


class TestShouldProcess:

    def test_no_buffer_returns_false(self, buffer_service, mock_redis_client):
        mock_redis_client.get.return_value = None
        assert buffer_service.should_process("5511999990000") is False

    @patch("app.services.message_buffer_service.settings")
    def test_debounce_trigger(self, mock_settings, buffer_service, mock_redis_client):
        """Retorna True se tempo desde última msg >= BUFFER_DEBOUNCE_SECONDS."""
        mock_settings.BUFFER_DEBOUNCE_SECONDS = 3
        mock_settings.BUFFER_MAX_WAIT_SECONDS = 10

        now = datetime.now()
        buffer_data = {
            "messages": ["Olá!"],
            "first_at": now.isoformat(),
            "last_at": (now - timedelta(seconds=4)).isoformat(),  # 4s ago
        }
        mock_redis_client.get.return_value = json.dumps(buffer_data)

        assert buffer_service.should_process("5511999990000") is True

    @patch("app.services.message_buffer_service.settings")
    def test_max_wait_trigger(self, mock_settings, buffer_service, mock_redis_client):
        """Retorna True se tempo desde primeira msg >= BUFFER_MAX_WAIT_SECONDS."""
        mock_settings.BUFFER_DEBOUNCE_SECONDS = 3
        mock_settings.BUFFER_MAX_WAIT_SECONDS = 10

        now = datetime.now()
        buffer_data = {
            "messages": ["msg1", "msg2", "msg3"],
            "first_at": (now - timedelta(seconds=11)).isoformat(),  # 11s ago
            "last_at": now.isoformat(),  # Just now (debounce not triggered)
        }
        mock_redis_client.get.return_value = json.dumps(buffer_data)

        assert buffer_service.should_process("5511999990000") is True

    @patch("app.services.message_buffer_service.settings")
    def test_not_ready_yet(self, mock_settings, buffer_service, mock_redis_client):
        """Retorna False se nem debounce nem max_wait atingidos."""
        mock_settings.BUFFER_DEBOUNCE_SECONDS = 3
        mock_settings.BUFFER_MAX_WAIT_SECONDS = 10

        now = datetime.now()
        buffer_data = {
            "messages": ["msg1"],
            "first_at": (now - timedelta(seconds=2)).isoformat(),  # 2s ago
            "last_at": (now - timedelta(seconds=1)).isoformat(),   # 1s ago
        }
        mock_redis_client.get.return_value = json.dumps(buffer_data)

        assert buffer_service.should_process("5511999990000") is False


# ═══════════════════════════════════════════════════════════════════════════
# GET AND CLEAR BUFFER
# ═══════════════════════════════════════════════════════════════════════════


class TestGetAndClearBuffer:

    def test_atomic_get_and_clear(self, buffer_service, mock_redis_client):
        """Retorna buffer e remove do Redis atomicamente."""
        buffer_data = {
            "messages": ["Olá!", "Tudo bem?"],
            "first_at": "2024-01-01T00:00:00",
            "last_at": "2024-01-01T00:00:05",
            "company_id": "company-1",
        }
        mock_pipe = mock_redis_client.pipeline.return_value
        mock_pipe.execute.return_value = [json.dumps(buffer_data), 1]

        result = buffer_service.get_and_clear_buffer("5511999990000")

        assert result is not None
        assert result["messages"] == ["Olá!", "Tudo bem?"]
        # Pipeline should have GET and DELETE calls
        mock_pipe.get.assert_called_once()
        mock_pipe.delete.assert_called_once()

    def test_returns_none_when_empty(self, buffer_service, mock_redis_client):
        mock_pipe = mock_redis_client.pipeline.return_value
        mock_pipe.execute.return_value = [None, 0]

        result = buffer_service.get_and_clear_buffer("5511999990000")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# COMBINE MESSAGES
# ═══════════════════════════════════════════════════════════════════════════


class TestCombineMessages:

    def test_single_message(self, buffer_service):
        buffer = {"messages": ["Olá!"]}
        assert buffer_service.get_combined_message(buffer) == "Olá!"

    def test_multiple_messages_joined_with_newline(self, buffer_service):
        buffer = {"messages": ["Olá!", "Tudo bem?", "Preciso de ajuda"]}
        combined = buffer_service.get_combined_message(buffer)
        assert combined == "Olá!\nTudo bem?\nPreciso de ajuda"

    def test_empty_messages_list(self, buffer_service):
        buffer = {"messages": []}
        assert buffer_service.get_combined_message(buffer) == ""

    def test_missing_messages_key(self, buffer_service):
        buffer = {}
        assert buffer_service.get_combined_message(buffer) == ""
