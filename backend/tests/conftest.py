"""
conftest.py — Configuração global dos testes.

Responsabilidades:
- Variáveis de ambiente mínimas para pydantic Settings()
- Fixtures compartilhadas entre todas as camadas (unit/integration/e2e)
- NÃO faz mocking de sys.modules aqui (movido para unit/conftest.py)
"""

import os

import pytest

# ---------------------------------------------------------------------------
# Variáveis de ambiente mínimas para o pydantic Settings() não falhar.
# Configuradas ANTES de qualquer import do app (settings é carregado em módulo).
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmNoYXJz")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DEBUG", "false")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_company_data():
    """Dados mínimos de uma company para testes."""
    return {
        "id": "aaaaaaaa-1111-2222-3333-444444444444",
        "company_name": "Test Corp",
        "status": "active",
        "plan_type": "starter",
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "llm_temperature": 0.7,
        "llm_max_tokens": 2000,
        "agent_enabled": True,
        "use_langchain": True,
    }


@pytest.fixture
def sample_user_data():
    """Dados mínimos de um user para testes."""
    return {
        "id": "bbbbbbbb-1111-2222-3333-444444444444",
        "email": "user@test.com",
        "first_name": "Test",
        "last_name": "User",
        "company_id": "aaaaaaaa-1111-2222-3333-444444444444",
        "role": "admin_company",
        "status": "active",
        "is_owner": True,
    }


@pytest.fixture
def sample_conversation_data(sample_company_data, sample_user_data):
    """Dados mínimos de uma conversa para testes."""
    return {
        "id": "cccccccc-1111-2222-3333-444444444444",
        "user_id": sample_user_data["id"],
        "session_id": "test-session-001",
        "company_id": sample_company_data["id"],
        "status": "open",
        "channel": "web",
    }


@pytest.fixture
def sample_agent_config():
    """Configuração mínima de agente para testes."""
    return {
        "guardrails_enabled": True,
        "allow_web_search": True,
        "url_validation_mode": "blacklist",
        "url_whitelist": [],
        "url_blacklist": [],
        "custom_blocked_patterns": [],
        "llama_guard_enabled": False,
        "presidio_enabled": False,
    }
