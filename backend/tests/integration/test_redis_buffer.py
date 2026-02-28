"""
Integration tests for Redis Message Buffer — Real Redis via Testcontainers.

Testa o ciclo de vida completo do buffer com Redis real:
add → should_process → get_and_clear → combine.

NOTA: Não importamos MessageBufferService no top-level porque
message_buffer_service.py cria um singleton no módulo que tenta
conectar ao Redis imediatamente.
"""

import json
import sys
import time
from unittest.mock import MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# BUFFER LIFECYCLE WITH REAL REDIS
# ═══════════════════════════════════════════════════════════════════════════


class TestBufferLifecycleRealRedis:

    @pytest.fixture
    def buffer_service(self, redis_client):
        """MessageBufferService atachado ao Redis do Testcontainer, sem singleton."""
        # Mock get_redis_client para o singleton do módulo não falhar
        from unittest.mock import patch
        with patch("app.core.redis.get_redis_client", return_value=redis_client):
            # Reimportar para garantir módulo real
            if "app.services.message_buffer_service" in sys.modules:
                del sys.modules["app.services.message_buffer_service"]
            from app.services.message_buffer_service import MessageBufferService

        svc = MessageBufferService.__new__(MessageBufferService)
        svc.redis = redis_client
        return svc

    def test_add_first_message_creates_buffer(self, buffer_service, redis_client):
        is_first = buffer_service.add_message(
            phone="5511999990001",
            message="Olá!",
            company_id="company-1",
            user_id="user-1",
            integration={"type": "whatsapp"},
            payload={"raw": "data"},
        )
        assert is_first is True

        # Verifica que foi salvo no Redis real
        key = buffer_service._get_key("5511999990001")
        raw = redis_client.get(key)
        assert raw is not None
        data = json.loads(raw)
        assert data["messages"] == ["Olá!"]

    def test_append_multiple_messages(self, buffer_service, redis_client):
        phone = "5511999990002"

        buffer_service.add_message(
            phone=phone, message="Msg 1", company_id="c1",
            user_id="u1", integration={}, payload={},
        )
        buffer_service.add_message(
            phone=phone, message="Msg 2", company_id="c1",
            user_id="u1", integration={}, payload={},
        )
        buffer_service.add_message(
            phone=phone, message="Msg 3", company_id="c1",
            user_id="u1", integration={}, payload={},
        )

        key = buffer_service._get_key(phone)
        data = json.loads(redis_client.get(key))
        assert data["messages"] == ["Msg 1", "Msg 2", "Msg 3"]

    def test_get_and_clear_removes_from_redis(self, buffer_service, redis_client):
        phone = "5511999990003"
        buffer_service.add_message(
            phone=phone, message="Test", company_id="c1",
            user_id="u1", integration={}, payload={},
        )

        result = buffer_service.get_and_clear_buffer(phone)
        assert result is not None
        assert result["messages"] == ["Test"]

        # Confirma que foi removido do Redis
        key = buffer_service._get_key(phone)
        assert redis_client.get(key) is None

    def test_full_lifecycle(self, buffer_service, redis_client):
        """Ciclo completo: add → combine → clear."""
        phone = "5511999990004"

        buffer_service.add_message(
            phone=phone, message="Olá!", company_id="c1",
            user_id="u1", integration={}, payload={},
        )
        buffer_service.add_message(
            phone=phone, message="Preciso de ajuda.", company_id="c1",
            user_id="u1", integration={}, payload={},
        )

        buffer = buffer_service.get_and_clear_buffer(phone)
        combined = buffer_service.get_combined_message(buffer)

        assert combined == "Olá!\nPreciso de ajuda."
        assert redis_client.get(buffer_service._get_key(phone)) is None

    def test_ttl_is_applied(self, buffer_service, redis_client):
        """Verifica que o buffer tem TTL configurado."""
        phone = "5511999990005"
        buffer_service.add_message(
            phone=phone, message="TTL test", company_id="c1",
            user_id="u1", integration={}, payload={},
        )
        key = buffer_service._get_key(phone)
        ttl = redis_client.ttl(key)
        assert ttl > 0  # TTL deve estar ativo

    def test_concurrent_buffers_are_isolated(self, buffer_service, redis_client):
        """Buffers de telefones diferentes são isolados."""
        phone_a = "5511999990006"
        phone_b = "5511999990007"

        buffer_service.add_message(
            phone=phone_a, message="A1", company_id="c1",
            user_id="u1", integration={}, payload={},
        )
        buffer_service.add_message(
            phone=phone_b, message="B1", company_id="c2",
            user_id="u2", integration={}, payload={},
        )

        buf_a = buffer_service.get_and_clear_buffer(phone_a)
        buf_b = buffer_service.get_and_clear_buffer(phone_b)

        assert buf_a["messages"] == ["A1"]
        assert buf_a["company_id"] == "c1"
        assert buf_b["messages"] == ["B1"]
        assert buf_b["company_id"] == "c2"
