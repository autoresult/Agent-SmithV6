"""
conftest.py — Configuração global dos testes de storage.

Problema: app/services/__init__.py importa TODOS os services em cascata,
incluindo AudioService, LangChainService, AgentGraph etc. que dependem de
pacotes pesados não instalados no ambiente de teste isolado.

Solução: pré-popular sys.modules com mocks ANTES da coleta dos testes.
Lista derivada de: grep -rh "^from |^import " app/ | grep -v "^from \."
"""

import os
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Variáveis de ambiente mínimas para o pydantic Settings() não falhar.
# Configuradas ANTES de qualquer import do app (settings é carregado em módulo).
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmNoYXJz")

# ---------------------------------------------------------------------------
# Módulos e sub-módulos que não precisam estar disponíveis para testar storage
# NOTA: requests e responses NÃO estão aqui — moto depende do requests real
# ---------------------------------------------------------------------------
_MOCKED_MODULES = [
    # LLM providers
    "openai",
    "anthropic",
    "groq",
    "cohere",
    "google.generativeai",
    "google.ai",
    "google.ai.generativelanguage",
    # LangChain (todos sub-módulos importados diretamente no app)
    "langchain",
    "langchain_core",
    "langchain_core.callbacks",
    "langchain_core.messages",
    "langchain_core.output_parsers",
    "langchain_core.outputs",
    "langchain_core.prompts",
    "langchain_core.runnables",
    "langchain_core.tools",
    "langchain_core.embeddings",
    "langchain_core.language_models",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_community",
    "langchain_experimental",
    "langchain_experimental.text_splitter",
    "langchain_google_genai",
    "langchain_text_splitters",
    # LangGraph (todos sub-módulos usados)
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.checkpoint",
    "langgraph.prebuilt",
    "langsmith",
    # Vector / embeddings
    "qdrant_client",
    "qdrant_client.models",
    "fastembed",
    # Database (incluir sub-módulos importados diretamente)
    "supabase",
    "supabase._async",
    "supabase._async.client",
    "supabase._sync",
    "supabase._sync.client",
    "psycopg",
    "psycopg_pool",
    "langgraph_checkpoint_postgres",
    # Cache / queues
    "redis",
    "apscheduler",
    "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "celery",
    # Document processing
    "PyPDF2",
    "docx",
    "tiktoken",
    # External services
    "stripe",
    "sendgrid",
    "sendgrid.helpers",
    "sendgrid.helpers.mail",
    "sentry_sdk",
    "slowapi",
    "slowapi.errors",
    "slowapi.util",
    "presidio_analyzer",
    "presidio_analyzer.nlp_engine",
    "presidio_anonymizer",
    "presidio_anonymizer.entities",
    "httpx",
    "tavily",
    # Retry / utils
    "tenacity",
    # Data processing
    "pandas",
    "tqdm",
    "cachetools",
    # "cryptography" NÃO deve ser mockado: moto depende de cryptography.hazmat
    "bcrypt",
    # NLP
    "spacy",
    # Slugify
    "slugify",
    "python_slugify",
    # uvicorn extras
    "uvicorn.middleware",
    "uvicorn.middleware.proxy_headers",
    # dotenv (python-dotenv)
    "dotenv",
    # MinIO SDK (não instalado no venv de testes)
    "minio",
    "minio.error",
]

for _mod in _MOCKED_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------
# Interceptar módulos internos do app que disparam cascades problemáticas.
# app.agents usa type annotations com classes mockadas (Optional[MagicMock])
# o que quebra o sistema de typing do Python 3.12 ao ser interpretado.
# ---------------------------------------------------------------------------
_APP_INTERNALS_TO_MOCK = [
    "app.agents",
    "app.agents.guardrails",
    "app.agents.graph",
    "app.agents.tools",
    "app.agents.tools.mcp_factory",
]
for _mod in _APP_INTERNALS_TO_MOCK:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
