# Test Suite Progress — Agent Smith V6 Backend

**Sessão**: 2026-02-28
**Status geral**: ✅ Unit (295/295) · ✅ Integration (13 confirmados) · ⚠️ E2E (em ajuste final)

---

## Arquivos de Documentação (Gemini Brain)

| Documento | Caminho completo |
|---|---|
| **Implementation Plan** | `/home/israelsantiago/.gemini/antigravity/brain/269737d8-b05b-4e1d-abfb-2c12e27854ad/implementation_plan.md` |
| **Task** | `/home/israelsantiago/.gemini/antigravity/brain/269737d8-b05b-4e1d-abfb-2c12e27854ad/task.md` |
| **Walkthrough** | `/home/israelsantiago/.gemini/antigravity/brain/269737d8-b05b-4e1d-abfb-2c12e27854ad/walkthrough.md` |
| **Claude Memory** | `/home/israelsantiago/.claude/projects/-home-israelsantiago-Agent-SmithV6/memory/MEMORY.md` |

---

## Progresso por Camada

### ✅ Unit Tests — 295/295 passando (~1.3s, sem Docker)

| Priority | Arquivo | Tests |
|---|---|---|
| P1 | `tests/unit/agents/test_guardrails.py` | ~80 |
| P1 | `tests/unit/workers/test_billing_core.py` | ~48 |
| P1 | `tests/unit/services/test_message_buffer_service.py` | ~15 |
| P1 | `tests/unit/services/test_encryption_service.py` | ~12 |
| P2 | `tests/unit/services/test_usage_service.py` | ~25 |
| P2 | `tests/unit/api/test_stripe_webhooks.py` | ~20 |
| P2 | `tests/unit/services/test_billing_service.py` | ~12 |
| P2 | `tests/unit/services/test_whatsapp_service.py` | ~8 |
| P2 | `tests/unit/services/test_email_service.py` | ~7 |
| P3 ★ | `tests/unit/agents/test_agent_utils.py` | 21 |
| P3 ★ | `tests/unit/agents/test_nodes.py` | 22 |
| P3 ★ | `tests/unit/api/test_webhook.py` | 20 |

★ Criado nesta sessão.

```bash
# Executar
cd backend && .venv/bin/python3 -m pytest tests/unit -v --tb=short
```

---

### ✅ Integration Tests — 35 escritos / 13 confirmados (Docker necessário)

| Arquivo | Container | Tests | Status |
|---|---|---|---|
| `tests/integration/test_database.py` | Postgres 16 | 7 | ✅ confirmado |
| `tests/integration/test_redis_buffer.py` | Redis 8.6.1 | 6 | ✅ confirmado |
| `tests/integration/test_qdrant_service.py` ★ | Qdrant v1.17.0 | 10 | ⏳ requer Docker |
| `tests/integration/test_storage_s3.py` ★ | SeaweedFS latest | 12 | ⏳ requer Docker |

★ Criado nesta sessão. `integration/conftest.py` também atualizado (MinIO → SeaweedFS, +Qdrant fixtures).

```bash
# Executar (SEPARADO dos unit tests — conflito de sys.modules)
cd backend && .venv/bin/python3 -m pytest tests/integration -v --tb=short
```

---

### ⚠️ E2E Tests — 36 escritos / ~11 passando na última execução

| Arquivo | Tests | Status |
|---|---|---|
| `tests/e2e/test_chat_flow.py` ★ | 6 | ⚠️ parcial |
| `tests/e2e/test_webhook_flow.py` ★ | 12 | ⚠️ pendente |
| `tests/e2e/test_billing_flow.py` ★ | 5 | ⚠️ pendente |
| `tests/e2e/test_document_flow.py` ★ | 13 | ⚠️ 11/13 passando |

★ Criado nesta sessão. `e2e/conftest.py` completamente reescrito.

```bash
# Executar
cd backend && .venv/bin/python3 -m pytest tests/e2e/ -v --tb=short -p no:cacheprovider
```

---

## Pendência Exata para Próxima Sessão

**1 fix em `tests/e2e/test_document_flow.py`** — `docs_app` fixture usa `patch()` como context manager, que expira antes dos requests chegarem ao endpoint.

```python
# ❌ ATUAL — patch expira quando o `with` fecha
with patch("app.api.documents.get_document_service", return_value=mock_doc_service):
    from app.api.documents import router as docs_router
    app.include_router(docs_router, prefix="/api")
return app, mock_doc_service, mock_ingestion  # patch já restaurado aqui!

# ✅ FIX — setattr direto no módulo (permanente durante o fixture)
import app.api.documents as docs_mod
docs_mod.get_document_service = lambda: mock_doc_service
docs_mod.get_ingestion_service = lambda: mock_ingestion
docs_mod.get_benchmark_service = lambda: MagicMock()
docs_mod.get_qdrant_service = lambda: MagicMock()
docs_mod.get_redis_client = lambda: MagicMock()
from app.api.documents import router as docs_router
app.include_router(docs_router, prefix="/api")
```

Após esse fix, rodar:
```bash
.venv/bin/python3 -m pytest tests/e2e/ -v --tb=short -p no:cacheprovider
# Esperado: ~33+ tests passando
```

---

## Arquivos de Teste no Filesystem

```
backend/tests/
├── conftest.py                          # fixtures globais (factories, env)
├── factories/
│   └── models.py
├── unit/
│   ├── conftest.py                      # stub packages + sys.modules mocking
│   ├── agents/
│   │   ├── test_guardrails.py
│   │   ├── test_nodes.py               ★ novo
│   │   └── test_agent_utils.py         ★ novo (fix AIMessage)
│   ├── api/
│   │   ├── test_stripe_webhooks.py
│   │   └── test_webhook.py             ★ novo
│   ├── services/
│   │   ├── test_billing_core.py
│   │   ├── test_billing_service.py
│   │   ├── test_email_service.py
│   │   ├── test_encryption_service.py
│   │   ├── test_message_buffer_service.py
│   │   ├── test_usage_service.py
│   │   └── test_whatsapp_service.py
│   └── workers/
│       └── test_billing_core.py
├── integration/
│   ├── conftest.py                      ★ atualizado (SeaweedFS, Qdrant)
│   ├── test_database.py
│   ├── test_redis_buffer.py
│   ├── test_qdrant_service.py          ★ novo
│   └── test_storage_s3.py             ★ novo
└── e2e/
    ├── conftest.py                      ★ reescrito (stub approach, sem Docker)
    ├── test_billing_flow.py            ★ novo
    ├── test_chat_flow.py               ★ novo
    ├── test_document_flow.py           ★ novo (1 fix pendente)
    └── test_webhook_flow.py            ★ novo
```
