#!/bin/bash
set -e

UPSTREAM_REMOTE="upstream"
ORIGIN_REMOTE="origin"
DATE=$(date +%Y%m%d)
INTEGRATION_BRANCH="integrate/upstream-${DATE}"

echo "======================================"
echo " Agent-SmithV6 Upstream Sync Script"
echo " Data: $DATE"
echo "======================================"

# Garantir que estamos em main limpo
git checkout main
if [ -n "$(git status --porcelain)" ]; then
  echo "ERRO: Working tree não está limpa. Faça commit ou stash antes."
  exit 1
fi

# 1. Buscar upstream
echo "[1/5] Fetching upstream..."
git fetch $UPSTREAM_REMOTE

# 2. Mostrar o que vai chegar
echo "[2/5] Novidades do upstream:"
git log main..${UPSTREAM_REMOTE}/main --oneline || echo "(nenhuma novidade)"
echo "Arquivos afetados:"
git diff main..${UPSTREAM_REMOTE}/main --name-only || true

# 3. Criar branch de integração
echo "[3/5] Criando branch de integração: $INTEGRATION_BRANCH"
git checkout -b $INTEGRATION_BRANCH

# 4. Rebase sobre upstream
echo "[4/5] Aplicando rebase sobre upstream/main..."
if ! git rebase ${UPSTREAM_REMOTE}/main; then
  echo ""
  echo "CONFLITO DETECTADO. Passos para resolver:"
  echo "  1. git status              → ver arquivos em conflito"
  echo "  2. edite os arquivos       → resolva os <<<<< ===== >>>>>"
  echo "  3. git add <arquivo>       → marque como resolvido"
  echo "  4. git rebase --continue   → continue o rebase"
  echo "  5. Execute este script novamente"
  exit 1
fi

# 5. Rodar testes
echo "[5/5] Rodando suíte de testes..."
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}/backend"
if python3 -m pytest tests/ -v --tb=short; then
  echo ""
  echo "======================================"
  echo " SUCESSO! Integração validada."
  echo " Para publicar no seu GitHub, execute:"
  echo ""
  echo "   git checkout main"
  echo "   git merge --ff-only $INTEGRATION_BRANCH"
  echo "   git push $ORIGIN_REMOTE main"
  echo "======================================"
else
  echo ""
  echo "FALHA: Testes não passaram. NÃO faça push para main."
  echo "Branch de integração preservado em: $INTEGRATION_BRANCH"
  exit 1
fi
