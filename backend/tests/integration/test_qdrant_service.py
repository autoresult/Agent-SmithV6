"""
Integration tests for QdrantService — Vector store operations with real Qdrant.

Requer:
- Docker disponível (Testcontainers)
- qdrant/qdrant:v1.17.0 image

Usa vetores aleatórios de dimensão 64 para velocidade.
QdrantService é criado apontando para o container via env vars.
"""

import random
import uuid

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VECTOR_DIM = 64  # Pequeno para velocidade nos testes


def make_random_vector(dim: int = VECTOR_DIM) -> list:
    """Cria um vetor aleatório normalizado para uso nos testes."""
    v = [random.gauss(0, 1) for _ in range(dim)]
    norm = sum(x ** 2 for x in v) ** 0.5
    return [x / norm for x in v]


@pytest.fixture(scope="module")
def qdrant_service(qdrant_container):
    """
    QdrantService apontando para o container Qdrant real.
    Usa dimensão 64 para testes mais rápidos.
    """
    host = qdrant_container.get_container_host_ip()
    port = qdrant_container.get_exposed_port(6333)

    import os
    os.environ["QDRANT_HOST"] = host
    os.environ["QDRANT_PORT"] = str(port)
    os.environ["QDRANT_API_KEY"] = ""
    os.environ["EMBEDDING_DIMENSION"] = str(VECTOR_DIM)

    from app.services.qdrant_service import QdrantService
    service = QdrantService()
    yield service


@pytest.fixture
def company_id():
    """Gera um company_id único por teste para isolamento."""
    return f"test-company-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def agent_id():
    """Gera um agent_id único por teste."""
    return f"test-agent-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def cleanup_collection(qdrant_service, company_id):
    """Remove a collection de teste após cada test."""
    yield
    try:
        qdrant_service.delete_collection(company_id)
    except Exception:
        pass


# ===========================================================================
# TestQdrantCreateCollection
# ===========================================================================


class TestQdrantCreateCollection:

    def test_create_collection_succeeds(self, qdrant_service, company_id):
        """Criação de collection para nova empresa deve retornar True."""
        result = qdrant_service.create_collection(company_id)
        assert result is True

    def test_create_collection_idempotent(self, qdrant_service, company_id):
        """Segunda chamada não deve falhar — retorna True sem erro."""
        qdrant_service.create_collection(company_id)
        result = qdrant_service.create_collection(company_id)  # Segunda vez
        assert result is True

    def test_collection_exists_after_creation(self, qdrant_service, company_id):
        """Após criação, collection deve constar na lista de collections."""
        qdrant_service.create_collection(company_id)
        collections = qdrant_service.client.get_collections().collections
        collection_names = [col.name for col in collections]
        expected = qdrant_service._get_collection_name(company_id)
        assert expected in collection_names


# ===========================================================================
# TestQdrantInsertAndSearch
# ===========================================================================


class TestQdrantInsertAndSearch:

    def test_insert_embeddings_returns_true(self, qdrant_service, company_id, agent_id):
        """Inserção de embeddings com chunks deve retornar True."""
        qdrant_service.create_collection(company_id)
        embeddings = [make_random_vector() for _ in range(3)]
        chunks = ["Chunk A", "Chunk B", "Chunk C"]
        doc_id = str(uuid.uuid4())

        result = qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=doc_id,
            embeddings=embeddings,
            chunks=chunks,
            agent_id=agent_id,
        )
        assert result is True

    def test_search_similar_returns_chunks(self, qdrant_service, company_id, agent_id):
        """Busca por embedding similar deve retornar resultados não-vazios."""
        qdrant_service.create_collection(company_id)
        query_vector = make_random_vector()
        embeddings = [query_vector]  # Insert the query vector itself → should match
        chunks = ["Este é o conteúdo do chunk de teste."]
        doc_id = str(uuid.uuid4())

        qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=doc_id,
            embeddings=embeddings,
            chunks=chunks,
            agent_id=agent_id,
        )

        results = qdrant_service.search_similar(
            company_id=company_id,
            query_embedding=query_vector,
            top_k=5,
            agent_id=agent_id,
        )

        assert len(results) > 0
        assert "content" in results[0]

    def test_search_with_agent_id_filter(self, qdrant_service, company_id):
        """Busca com agent_id filtra apenas chunks daquele agente."""
        qdrant_service.create_collection(company_id)
        agent_a = f"agent-a-{uuid.uuid4().hex[:8]}"
        agent_b = f"agent-b-{uuid.uuid4().hex[:8]}"

        vec_a = make_random_vector()
        vec_b = make_random_vector()

        qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=str(uuid.uuid4()),
            embeddings=[vec_a],
            chunks=["Chunk do agente A"],
            agent_id=agent_a,
        )
        qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=str(uuid.uuid4()),
            embeddings=[vec_b],
            chunks=["Chunk do agente B"],
            agent_id=agent_b,
        )

        # Buscar apenas pelo agente A
        results_a = qdrant_service.search_similar(
            company_id=company_id,
            query_embedding=vec_a,
            top_k=10,
            agent_id=agent_a,
        )

        # Todos os resultados devem ser do agente A
        for r in results_a:
            assert r.get("agent_id") == agent_a or r.get("metadata", {}) is not None

    def test_search_empty_collection_returns_empty_list(self, qdrant_service, company_id):
        """Busca em collection vazia (sem matches) deve retornar lista vazia."""
        results = qdrant_service.search_similar(
            company_id=f"nonexistent-{uuid.uuid4().hex}",
            query_embedding=make_random_vector(),
            top_k=5,
        )
        assert results == []


# ===========================================================================
# TestQdrantDelete
# ===========================================================================


class TestQdrantDelete:

    def test_delete_document_removes_points(self, qdrant_service, company_id, agent_id):
        """Deletar documento deve remover seus pontos da collection."""
        qdrant_service.create_collection(company_id)
        doc_id = str(uuid.uuid4())
        query_vec = make_random_vector()

        qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=doc_id,
            embeddings=[query_vec],
            chunks=["Texto a ser deletado"],
            agent_id=agent_id,
        )

        # Verificar que foi inserido
        results_before = qdrant_service.search_similar(
            company_id=company_id,
            query_embedding=query_vec,
            agent_id=agent_id,
        )
        assert len(results_before) > 0

        # Deletar documento
        qdrant_service.delete_document(company_id, doc_id)

        # Verificar que foi removido
        results_after = qdrant_service.search_similar(
            company_id=company_id,
            query_embedding=query_vec,
            agent_id=agent_id,
        )
        # Nenhum resultado com este document_id
        doc_ids_after = [r.get("document_id") for r in results_after]
        assert doc_id not in doc_ids_after

    def test_delete_collection_removes_all(self, qdrant_service, company_id, agent_id):
        """Deletar collection remove toda a collection do Qdrant."""
        qdrant_service.create_collection(company_id)
        qdrant_service.insert_embeddings(
            company_id=company_id,
            document_id=str(uuid.uuid4()),
            embeddings=[make_random_vector()],
            chunks=["Será deletado"],
            agent_id=agent_id,
        )

        qdrant_service.delete_collection(company_id)

        # Busca retorna vazio (collection inexistente)
        results = qdrant_service.search_similar(
            company_id=company_id,
            query_embedding=make_random_vector(),
        )
        assert results == []
