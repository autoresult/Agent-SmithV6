# Architecture Decision Records (ADR) — Agent-SmithV6

> Registro das decisões arquiteturais tomadas neste fork.
> Cada ADR descreve o contexto, a decisão e as consequências.

---

## ADR-001: Storage Abstraction Layer com Factory Pattern

**Data:** Fevereiro/2026
**Status:** Implementado ✅

### Contexto

O projeto original usava MinIO como único serviço de armazenamento de objetos.
Em outubro/2025, MinIO descontinuou as imagens Docker oficiais da versão Community,
tornando o setup local frágil e sem suporte.

### Decisão

Implementar uma camada de abstração de storage com Factory Pattern, permitindo
trocar o provedor via variável de ambiente sem alterar código de negócio.

**Arquivos criados:**

| Arquivo | Responsabilidade |
|---------|-----------------|
| `backend/app/services/storage/base.py` | Protocolo `StorageProvider` (runtime_checkable) — contrato público |
| `backend/app/services/storage/factory.py` | `get_storage_service()` — singleton por provider |
| `backend/app/services/storage/seaweedfs_service.py` | Implementação principal (SeaweedFS via boto3 S3 API) |
| `backend/app/services/minio_service.py` | Implementação legada (MinIO SDK) — mantida para rollback |

**Interface do protocolo (`StorageProvider`):**
- `upload_file(company_id, document_id, filename, data)` → estrutura `{company_id}/{document_id}/{filename}`
- `upload_object(path, data)` → upload em path arbitrário (JSON, manifests)
- `download_file(path)` → recuperar objeto
- `delete_file(path)` → remover objeto único
- `delete_folder(prefix)` → remover árvore por prefixo
- `get_file_url(path, expires)` → URL pré-assinada (padrão: 3600s)

**Switch de provider:**
```bash
# .env
STORAGE_PROVIDER=seaweedfs   # padrão
STORAGE_PROVIDER=minio       # rollback
```

**Portas SeaweedFS:**
- `8333` — S3 API (compatível com boto3)
- `9333` — Master
- `8888` — Filer
- `23646` — Admin UI

### Consequências

- ✅ Nenhum código de negócio importa MinIO ou SeaweedFS diretamente
- ✅ Rollback via variável de ambiente, sem alteração de código
- ✅ 37 testes cobrindo factory, implementação e conformidade de protocolo
- ✅ Novos providers podem ser adicionados implementando o protocolo `StorageProvider`
- ⚠️ Dependência de boto3 para SeaweedFS (em vez do SDK oficial do SeaweedFS)

---

## ADR-002: Fork Management e Sincronização com Upstream

**Data:** Fevereiro/2026
**Status:** Implementado ✅

### Contexto

Este projeto é derivado de `LionLabsCommunity/Agent-SmithV6` (acesso read-only).
O upstream lança releases periódicas com melhorias. Precisamos absorver essas
novidades sem perder as contribuições locais (ex: storage layer, fixes).

### Decisão

**Topologia de remotes (Triangular Workflow):**

```
upstream → https://github.com/LionLabsCommunity/Agent-SmithV6.git  (fetch only)
origin   → https://github.com/autoresult/Agent-SmithV6.git         (fetch + push)
```

**Fluxo de integração (executado a cada release do upstream):**

```bash
./backend/scripts/sync_upstream.sh
```

O script automatiza:
1. `git fetch upstream` — busca novidades
2. Cria branch isolado `integrate/upstream-YYYYMMDD`
3. `git rebase upstream/main` — reposiciona commits locais
4. Executa `python3 -m pytest tests/ -v` — gate de qualidade
5. Instrui o merge em `main` apenas se testes passarem

**Rede de segurança (patches):**
- Commits locais exportados como patches em `.patches/local/`
- Plano B: se rebase falhar, `git am .patches/local/*.patch` sobre base limpa

### Princípio de Baixo Footprint

Adições locais devem preferir **criar arquivos novos** em vez de modificar
arquivos que o upstream também mantém:

| Prática | Exemplo |
|---------|---------|
| Novos diretórios isolados | `backend/app/services/storage/` |
| Override de Docker Compose | `docker-compose.override.yml` (aplicado automaticamente) |
| Dependências extras | `requirements.local.txt` |
| Configuração via env | `STORAGE_PROVIDER=seaweedfs` em `.env` |

**Arquivos com maior risco de conflito em releases:**
- `backend/app/services/__init__.py`
- `backend/app/core/config.py`
- `backend/requirements.txt`
- `backend/docker-compose.yml`
- `package.json` / `next.config.js`

### Consequências

- ✅ Workflow reproduzível com um único comando
- ✅ `main` nunca recebe código com testes quebrando
- ✅ Histórico linear após rebase (fácil de auditar)
- ✅ Patches como rede de segurança absoluta
- ⚠️ Conflitos manuais ainda possíveis nos arquivos de alto risco listados acima

---

## Histórico de Releases Integradas

| Data | Versão Upstream | Conflitos | Testes |
|------|----------------|-----------|--------|
| *(aguardando 03/03/26)* | — | — | — |
