"""
conftest.py — Configuração para testes de integração com Testcontainers.

Responsabilidades:
- Lifecycle dos containers Docker (session-scoped para performance)
- Fixtures que fornecem clientes conectados a serviços reais
- Schema SQL aplicado ao Postgres container
- Auto-marca testes com @pytest.mark.integration
"""

import pytest

# ---------------------------------------------------------------------------
# Auto-aplicar @pytest.mark.integration em todos os testes deste pacote
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    """Aplica mark 'integration' automaticamente em testes de tests/integration/."""
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ---------------------------------------------------------------------------
# SQL mínimo para criar tabelas necessárias nos testes de integração.
# Extraído do Supabase migrations (backend/supabase/migrations/migration.sql).
# ---------------------------------------------------------------------------
TEST_SCHEMA_SQL = """
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS companies (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_name varchar(255) NOT NULL,
    legal_name varchar(255),
    cnpj varchar(18),
    plan_type varchar(50) DEFAULT 'starter',
    status varchar(20) DEFAULT 'active',
    primary_contact_email varchar(255),
    llm_provider varchar(50),
    llm_model varchar(100),
    llm_api_key text,
    llm_temperature numeric(3,2) DEFAULT 0.7,
    llm_max_tokens integer DEFAULT 2000,
    agent_enabled boolean DEFAULT false,
    use_langchain boolean DEFAULT false,
    agent_system_prompt text,
    allow_web_search boolean DEFAULT true,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    CONSTRAINT companies_status_check CHECK (status IN ('active','trial','suspended','cancelled'))
);

CREATE TABLE IF NOT EXISTS users_v2 (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    first_name varchar(255),
    last_name varchar(255),
    email varchar(255) UNIQUE NOT NULL,
    password_hash varchar(255),
    cpf varchar(15),
    phone varchar(20),
    birth_date date,
    company_id uuid REFERENCES companies(id),
    status varchar(20) DEFAULT 'active',
    role varchar(20) DEFAULT 'member',
    is_owner boolean DEFAULT false,
    terms_accepted_at timestamp,
    privacy_policy_accepted_at timestamp,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    user_id uuid NOT NULL,
    session_id text NOT NULL,
    title text,
    company_id uuid REFERENCES companies(id),
    status varchar(20) DEFAULT 'open',
    channel varchar(20) DEFAULT 'web',
    last_message_preview text,
    unread_count integer DEFAULT 0,
    agent_name text DEFAULT 'Smith Agent',
    user_name text,
    user_phone text,
    last_message_at timestamp with time zone DEFAULT now(),
    agent_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations(id),
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    type text DEFAULT 'text' CHECK (type IN ('text', 'voice')),
    audio_url text,
    image_url text,
    sender_user_id uuid
);

CREATE TABLE IF NOT EXISTS conversation_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    timestamp timestamp with time zone DEFAULT now(),
    company_id uuid NOT NULL,
    user_id uuid NOT NULL,
    session_id text NOT NULL,
    user_question text NOT NULL,
    assistant_response text NOT NULL,
    llm_provider text NOT NULL,
    llm_model text NOT NULL,
    llm_temperature double precision NOT NULL,
    tokens_input integer,
    tokens_output integer,
    tokens_total integer,
    rag_chunks jsonb,
    rag_chunks_count integer DEFAULT 0,
    response_time_ms integer,
    rag_search_time_ms integer,
    status text DEFAULT 'success',
    error_message text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    name varchar(100) NOT NULL,
    slug varchar(50) NOT NULL,
    description text,
    monthly_price numeric(10,2) NOT NULL,
    credits_limit integer NOT NULL,
    storage_limit_mb integer NOT NULL,
    max_users integer DEFAULT 1,
    features jsonb,
    is_active boolean DEFAULT true,
    price_brl numeric(10,2),
    stripe_product_id varchar(100),
    stripe_price_id varchar(100),
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_id uuid REFERENCES companies(id),
    plan_id uuid REFERENCES plans(id),
    status varchar(20) DEFAULT 'active',
    current_period_start timestamp with time zone,
    current_period_end timestamp with time zone,
    stripe_subscription_id varchar(100),
    stripe_customer_id varchar(100),
    cancel_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT subscriptions_status_check CHECK (status IN ('active','cancelled','past_due','trialing'))
);

CREATE TABLE IF NOT EXISTS company_credits (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_id uuid REFERENCES companies(id),
    balance_brl numeric(10,4) DEFAULT 0,
    alert_80_sent boolean DEFAULT false,
    alert_100_sent boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_id uuid,
    agent_id uuid,
    type varchar(20) NOT NULL CHECK (type IN ('subscription','topup','consumption','refund','bonus')),
    amount_brl numeric(10,4) NOT NULL,
    balance_after numeric(10,4),
    model_name varchar(100),
    tokens_input integer,
    tokens_output integer,
    description text,
    stripe_payment_id varchar(100),
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES companies(id),
    file_name text NOT NULL,
    file_type text NOT NULL CHECK (file_type IN ('pdf','docx','txt','md','csv')),
    file_size integer NOT NULL CHECK (file_size > 0),
    minio_path text NOT NULL,
    qdrant_collection text NOT NULL,
    status text DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','failed')),
    error_message text,
    chunks_count integer DEFAULT 0 CHECK (chunks_count >= 0),
    processed_at timestamp with time zone,
    agent_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integrations (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES companies(id),
    name varchar(100) NOT NULL,
    type varchar(50) NOT NULL,
    status varchar(20) DEFAULT 'active',
    config jsonb,
    credentials jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);
"""


# ---------------------------------------------------------------------------
# Testcontainers — Session-scoped para reutilização entre testes
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL container para testes de integração."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        image="postgres:16-alpine",
        username="test",
        password="test",
        dbname="test_db",
    ) as pg:
        # Aplicar schema de testes
        import psycopg

        conn_url = pg.get_connection_url()
        # testcontainers pode retornar URL com driver SQLAlchemy, converter para psycopg puro
        conn_url = conn_url.replace("postgresql+psycopg2://", "postgresql://")
        conn_url = conn_url.replace("postgresql+psycopg://", "postgresql://")

        with psycopg.connect(conn_url) as conn:
            conn.execute(TEST_SCHEMA_SQL)
            conn.commit()

        yield pg


@pytest.fixture(scope="session")
def redis_container():
    """Redis container para testes de integração."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:8.6.1-alpine") as rd:
        yield rd


@pytest.fixture(scope="session")
def seaweedfs_container():
    """
    SeaweedFS all-in-one container com S3 API na porta 8333.
    Usa GenericContainer pois não há módulo oficial testcontainers para SeaweedFS.
    """
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    container = (
        DockerContainer("chrislusf/seaweedfs:latest")
        .with_command("server -s3")
        .with_exposed_ports(8333)
    )
    with container:
        wait_for_logs(container, "S3 API available", timeout=60)
        yield container


@pytest.fixture(scope="session")
def qdrant_container():
    """Qdrant container para testes de integração (módulo oficial)."""
    from testcontainers.qdrant import QdrantContainer

    with QdrantContainer("qdrant/qdrant:v1.17.0") as qt:
        yield qt


# ---------------------------------------------------------------------------
# Client fixtures conectados aos containers
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_connection(postgres_container):
    """Conexão Postgres limpa (com rollback automático via savepoint)."""
    import psycopg

    conn_url = postgres_container.get_connection_url()
    conn_url = conn_url.replace("postgresql+psycopg2://", "postgresql://")
    conn_url = conn_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(conn_url) as conn:
        # Criar savepoint para rollback entre testes
        conn.execute("BEGIN")
        yield conn
        conn.execute("ROLLBACK")


@pytest.fixture
def redis_client(redis_container):
    """Redis client conectado ao container, limpo entre testes."""
    import redis

    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client = redis.Redis(host=host, port=int(port), decode_responses=True)
    yield client
    client.flushdb()  # Limpa dados entre testes


@pytest.fixture
def s3_client(seaweedfs_container):
    """
    boto3 S3 client com path-style addressing apontando para SeaweedFS container.
    Cria o bucket de teste e garante limpeza ao final.
    """
    import boto3
    from botocore.config import Config

    host = seaweedfs_container.get_container_host_ip()
    port = seaweedfs_container.get_exposed_port(8333)
    endpoint_url = f"http://{host}:{port}"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="any",
        aws_secret_access_key="any",
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )

    bucket = "test-bucket"
    try:
        client.create_bucket(Bucket=bucket)
    except client.exceptions.BucketAlreadyExists:
        pass
    except Exception:
        pass  # Bucket may already exist

    yield client, bucket

    # Cleanup: remover objetos do bucket
    try:
        objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
        for obj in objects:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
    except Exception:
        pass


@pytest.fixture
def qdrant_client_real(qdrant_container):
    """QdrantClient conectado ao container real."""
    from qdrant_client import QdrantClient

    host = qdrant_container.get_container_host_ip()
    port = qdrant_container.get_exposed_port(6333)
    return QdrantClient(host=host, port=int(port))
