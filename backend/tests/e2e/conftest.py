"""
conftest.py — Configuração para testes E2E (End-to-End).

Estratégia:
  - Todos os serviços externos (Supabase, LLMs, WhatsApp, Stripe) mockados
  - Usa o mesmo stub package approach do conftest unitário para
    prevenir cascade de imports pesados (langchain, mcp_factory, etc.)
  - Não requer Docker/Testcontainers — E2E aqui = HTTP layer + business logic
  - e2e_app: FastAPI app mínimo com webhook + stripe routers
  - e2e_client: httpx.AsyncClient conectado ao e2e_app

Nota sobre os Stubs:
  app.agents, app.services e app.api recebem ModuleType stubs (não MagicMock),
  o que previne a execução dos seus __init__.py pesados, mas mantém o
  __path__ real para que submodule imports funcionem normalmente.
"""

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Auto-aplicar @pytest.mark.e2e em todos os testes deste pacote
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Aplica mark 'e2e' automaticamente em testes de tests/e2e/."""
    for item in items:
        if "/e2e/" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


# ---------------------------------------------------------------------------
# 1) Módulos externos pesados → MagicMock em sys.modules
# ---------------------------------------------------------------------------

_E2E_MOCKED_MODULES = [
    # Supabase (cloud SDK)
    "supabase", "supabase._async", "supabase._async.client",
    "supabase._sync", "supabase._sync.client",
    # LLM providers
    "openai", "anthropic", "groq",
    "langchain", "langchain_core",
    "langchain_core.callbacks", "langchain_core.messages",
    "langchain_core.output_parsers", "langchain_core.outputs",
    "langchain_core.prompts", "langchain_core.runnables",
    "langchain_core.tools", "langchain_core.embeddings",
    "langchain_core.language_models",
    "langchain_openai", "langchain_anthropic", "langchain_community",
    "langchain_experimental", "langchain_experimental.text_splitter",
    "langchain_text_splitters", "langchain_google_genai",
    # LangGraph
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.prebuilt", "langsmith",
    # Vector
    "qdrant_client", "qdrant_client.models", "fastembed",
    # External
    "stripe",
    "sendgrid", "sendgrid.helpers", "sendgrid.helpers.mail",
    "sentry_sdk",
    "presidio_analyzer", "presidio_analyzer.nlp_engine",
    "presidio_anonymizer", "presidio_anonymizer.entities",
    "tavily",
    # Document
    "PyPDF2", "docx", "tiktoken",
    # Utils
    "tenacity",
    "pandas", "tqdm", "cachetools", "bcrypt", "spacy",
    "slugify", "python_slugify",
    # Scheduler
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    # DB extras
    "psycopg_pool", "langgraph_checkpoint_postgres",
    # Storage
    "minio", "minio.error",
]

for _mod in _E2E_MOCKED_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# 2) Stub packages para app.agents, app.services e app.api
#    (previne execução dos __init__.py que causam cascatas de import)
# ---------------------------------------------------------------------------

import app  # noqa: E402

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_stub_package(name: str, real_path: str):
    """Cria um stub de package em sys.modules com __path__ real para submodule discovery."""
    mod = types.ModuleType(name)
    mod.__path__ = [real_path]
    mod.__package__ = name
    mod.__file__ = os.path.join(real_path, "__init__.py")
    sys.modules[name] = mod
    return mod


_agents_stub = _make_stub_package("app.agents", os.path.join(_BACKEND_DIR, "app", "agents"))
_services_stub = _make_stub_package("app.services", os.path.join(_BACKEND_DIR, "app", "services"))
_api_stub = _make_stub_package("app.api", os.path.join(_BACKEND_DIR, "app", "api"))
_workers_stub = _make_stub_package("app.workers", os.path.join(_BACKEND_DIR, "app", "workers"))

app.agents = _agents_stub
app.services = _services_stub
app.api = _api_stub
app.workers = _workers_stub


# ---------------------------------------------------------------------------
# 3) Submodulos pesados → MagicMock (dentro dos stubs acima)
# ---------------------------------------------------------------------------

_HEAVY_SUBMODULES = [
    # app.agents heavy
    "app.agents.graph",
    "app.agents.tools",
    "app.agents.tools.mcp_factory",
    # app.services heavy
    "app.services.llama_guard_service",
    "app.services.presidio_service",
    "app.services.audio_service",
    "app.services.langchain_service",
    "app.services.agent_service",
    "app.services.mcp_gateway_service",
    "app.services.mcp_oauth_service",
    "app.services.memory_service",
    "app.services.benchmark_service",
    "app.services.qdrant_service",
    "app.services.tavily_service",
    "app.services.integration_service",
    "app.services.whatsapp_service",
    "app.services.message_buffer_service",
    "app.services.billing_service",
    "app.services.email_service",
    "app.services.shopify_auth",
    "app.services.shopify_catalog",
    "app.services.storefront_mcp",
    "app.services.ucp_discovery",
    "app.services.ucp_service",
    "app.services.ucp_transport",
    "app.services.document_service",
    "app.services.ingestion_service",
    "app.services.minio_service",
    "app.services.storage",
    "app.services.rerank_service",
    "app.services.search_service",
    # app.api heavy (routers testados são reimportados nos fixtures)
    "app.api.chat",
    "app.api.agents",
    "app.api.billing",
    "app.api.billing_admin",
    "app.api.plans",
    "app.api.pricing",
    "app.api.agent_config",
    "app.api.stripe_checkout",
    "app.api.mcp",
    "app.api.ucp",
]

for _mod in _HEAVY_SUBMODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# Fixtures principais
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_app():
    """
    FastAPI app para testes E2E:
    - Sem dependências externas reais (sem Docker/Testcontainers)
    - Todos os singletons externos mockados
    - Webhook + Stripe routers registrados

    Nota: os imports de webhook e stripe_webhooks são feitos aqui (dentro
    do fixture) para que ocorram DEPOIS dos stubs estarem configurados.
    """
    import importlib

    from fastapi import FastAPI

    app_instance = FastAPI(title="E2E Test App")

    # Forçar reimport dos routers (caso tenham sido cacheados como MagicMock)
    for mod_name in ["app.api.webhook", "app.api.stripe_webhooks"]:
        sys.modules.pop(mod_name, None)

    # Importar módulos reais dos routers
    webhook_mod = importlib.import_module("app.api.webhook")
    stripe_mod = importlib.import_module("app.api.stripe_webhooks")

    # Substituir singletons do webhook por mocks
    mock_supabase = MagicMock()
    mock_supabase.client = MagicMock()
    mock_table = MagicMock()
    for method in ["select", "eq", "limit", "single", "insert", "update", "is_", "order"]:
        getattr(mock_table, method).return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])
    mock_supabase.client.table.return_value = mock_table

    webhook_mod.supabase = mock_supabase
    webhook_mod.integration_service = MagicMock()
    webhook_mod.whatsapp_service = MagicMock()

    app_instance.include_router(webhook_mod.router)
    app_instance.include_router(stripe_mod.router)

    return app_instance


@pytest.fixture
async def e2e_client(e2e_app):
    """httpx.AsyncClient conectado ao e2e_app via ASGITransport."""
    import httpx
    from httpx import ASGITransport

    async with httpx.AsyncClient(
        transport=ASGITransport(app=e2e_app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_billing_service():
    """Mock de billing service com saldo suficiente por padrão."""
    mock = MagicMock()
    mock.has_sufficient_balance.return_value = True
    return mock


@pytest.fixture
def mock_langchain_service():
    """Mock de LangChainService com resposta padrão."""
    mock = MagicMock()
    mock.process_message = AsyncMock(return_value=("Resposta do assistente.", {}))
    return mock
