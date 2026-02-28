"""
conftest.py — Configuração para testes unitários.

Responsabilidades:
- Mock de sys.modules pesados (LangChain, LLMs, etc) ANTES da coleta
- Fixtures específicas para testes unitários (mocked dependencies)
- Aplicar mark @pytest.mark.unit automaticamente em todos os testes deste pacote

Estratégia de mock:
  1. Mock de dependências externas pesadas (LangChain, LLMs, etc.)
  2. Substituir parent packages (app.agents, app.services) por ModuleType stubs
     para que submodule imports funcionem normalmente
  3. Mock individual de submodulos pesados
  4. Re-importar módulos sob teste como módulos REAIS
"""

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1) Módulos EXTERNOS que não precisam estar disponíveis para testes unitários.
# ---------------------------------------------------------------------------
_MOCKED_MODULES = [
    # LLM providers
    "openai", "anthropic", "groq", "cohere",
    "google.generativeai", "google.ai", "google.ai.generativelanguage",
    # LangChain
    "langchain", "langchain_core",
    "langchain_core.callbacks", "langchain_core.messages",
    "langchain_core.output_parsers", "langchain_core.outputs",
    "langchain_core.prompts", "langchain_core.runnables",
    "langchain_core.tools", "langchain_core.embeddings",
    "langchain_core.language_models",
    "langchain_openai", "langchain_anthropic", "langchain_community",
    "langchain_experimental", "langchain_experimental.text_splitter",
    "langchain_google_genai", "langchain_text_splitters",
    # LangGraph
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.prebuilt", "langsmith",
    # Vector / embeddings
    "qdrant_client", "qdrant_client.models", "fastembed",
    # Database
    "supabase", "supabase._async", "supabase._async.client",
    "supabase._sync", "supabase._sync.client",
    "psycopg", "psycopg_pool", "langgraph_checkpoint_postgres",
    # Cache / queues
    "redis",
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    "celery",
    # Document processing
    "PyPDF2", "docx", "tiktoken",
    # External services
    "stripe",
    "sendgrid", "sendgrid.helpers", "sendgrid.helpers.mail",
    "sentry_sdk",
    "slowapi", "slowapi.errors", "slowapi.util",
    "presidio_analyzer", "presidio_analyzer.nlp_engine",
    "presidio_anonymizer", "presidio_anonymizer.entities",
    "httpx", "tavily",
    # Retry / utils
    "tenacity",
    # Data processing
    "pandas", "tqdm", "cachetools", "bcrypt",
    # NLP
    "spacy",
    # Slugify
    "slugify", "python_slugify",
    # uvicorn extras
    "uvicorn.middleware", "uvicorn.middleware.proxy_headers",
    # dotenv
    "dotenv",
    # MinIO SDK
    "minio", "minio.error",
]

for _mod in _MOCKED_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# 2) Substituir app.agents e app.services por ModuleType stubs COM paths reais.
#    Isso previne que seus __init__.py sejam executados (cascatas),
#    mas permite submodule imports: `from app.agents.guardrails import X`.
# ---------------------------------------------------------------------------
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar app e app.core normalmente (Settings já tem env vars do root conftest)
import app
import app.core  # noqa: F401 — necessário para Settings()


def _make_stub_package(name: str, real_path: str):
    """Cria um stub de package em sys.modules com path real para submodule discovery."""
    mod = types.ModuleType(name)
    mod.__path__ = [real_path]
    mod.__package__ = name
    mod.__file__ = os.path.join(real_path, "__init__.py")
    sys.modules[name] = mod
    return mod


# Stub packages — substitui __init__.py real (que faz imports pesados)
# mas mantém o path real para que Python encontre submodulos no filesystem
_agents_stub = _make_stub_package("app.agents", os.path.join(_BACKEND_DIR, "app", "agents"))
_services_stub = _make_stub_package("app.services", os.path.join(_BACKEND_DIR, "app", "services"))
_api_stub = _make_stub_package("app.api", os.path.join(_BACKEND_DIR, "app", "api"))
_workers_stub = _make_stub_package("app.workers", os.path.join(_BACKEND_DIR, "app", "workers"))

# Link stubs como atributos do módulo app para que monkeypatch funcione
app.agents = _agents_stub
app.services = _services_stub
app.api = _api_stub
app.workers = _workers_stub


# ---------------------------------------------------------------------------
# 3) Mock de submodulos pesados ESPECÍFICOS (dentro dos stubs acima).
#    Estes são os submodulos que NÃO vamos testar diretamente.
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
    # app.api heavy (webhook is in _MODULES_TO_REIMPORT — tested directly)
    "app.api.chat",
    "app.api.agents",
    "app.api.documents",
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
# 4) Re-importar módulos sob teste como módulos REAIS.
#    Agora que os parent packages são stubs e dependências pesadas são mocks,
#    Python consegue importar o módulo real sem cascatas.
# ---------------------------------------------------------------------------
_MODULES_TO_REIMPORT = [
    "app.agents.guardrails",
    "app.services.encryption_service",
    "app.services.message_buffer_service",
    # Priority 2 modules
    "app.services.usage_service",
    "app.services.billing_service",
    "app.services.whatsapp_service",
    "app.services.email_service",
    "app.api.stripe_webhooks",
    "app.workers.billing_core",
    # Priority 3 modules
    "app.agents.nodes",
    "app.api.webhook",
]

for _mod_name in _MODULES_TO_REIMPORT:
    try:
        sys.modules.pop(_mod_name, None)
        real_mod = importlib.import_module(_mod_name)
        sys.modules[_mod_name] = real_mod

        # Também seta como atributo do parent stub
        parts = _mod_name.rsplit(".", 1)
        if len(parts) == 2:
            parent_mod = sys.modules.get(parts[0])
            if parent_mod is not None:
                setattr(parent_mod, parts[1], real_mod)
    except Exception as e:
        import warnings
        warnings.warn(f"Failed to reimport {_mod_name}: {e}")


# ---------------------------------------------------------------------------
# Auto-aplicar @pytest.mark.unit em todos os testes deste pacote
# ---------------------------------------------------------------------------
def pytest_collection_modifyitems(config, items):
    """Aplica mark 'unit' automaticamente em testes de tests/unit/."""
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


# ---------------------------------------------------------------------------
# Fixtures de mock comuns para testes unitários
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_supabase_client(mocker):
    """Mock completo do SupabaseClient para testes unitários."""
    mock_client = MagicMock()

    mock_table = MagicMock()
    mock_client.client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.neq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.maybe_single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    return mock_client


@pytest.fixture
def mock_redis_client(mocker):
    """Mock do Redis client para testes unitários."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.ping.return_value = True

    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_pipe.execute.return_value = [None, 0]

    return mock_redis


@pytest.fixture
def mock_stripe(mocker):
    """Mock do Stripe SDK para testes unitários."""
    mock = MagicMock()
    mocker.patch.dict(sys.modules, {"stripe": mock})
    return mock
