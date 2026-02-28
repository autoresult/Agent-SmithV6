"""
Integration tests for PostgreSQL database operations via Testcontainers.

Testa CRUD real no Postgres: companies, conversations, messages.
"""

import uuid

import pytest


class TestCompanyCrud:
    """Testa operações CRUD na tabela companies."""

    def test_insert_and_select_company(self, pg_connection):
        company_id = str(uuid.uuid4())
        pg_connection.execute(
            """
            INSERT INTO companies (id, company_name, status, plan_type)
            VALUES (%s, %s, %s, %s)
            """,
            (company_id, "Test Corp", "active", "starter"),
        )

        result = pg_connection.execute(
            "SELECT company_name, status FROM companies WHERE id = %s",
            (company_id,),
        ).fetchone()

        assert result[0] == "Test Corp"
        assert result[1] == "active"

    def test_company_status_constraint(self, pg_connection):
        """Status fora da constraint deve falhar."""
        with pytest.raises(Exception):
            pg_connection.execute(
                """
                INSERT INTO companies (id, company_name, status)
                VALUES (%s, %s, %s)
                """,
                (str(uuid.uuid4()), "Bad Corp", "invalid_status"),
            )


class TestConversationAndMessages:
    """Testa operações em conversations e messages."""

    def test_create_conversation_and_messages(self, pg_connection):
        company_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        # Create company first (FK reference)
        pg_connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (%s, %s)",
            (company_id, "Test Corp"),
        )

        # Create conversation
        pg_connection.execute(
            """
            INSERT INTO conversations (id, user_id, session_id, company_id)
            VALUES (%s, %s, %s, %s)
            """,
            (conv_id, user_id, "session-001", company_id),
        )

        # Insert messages
        pg_connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, %s, %s)
            """,
            (conv_id, "user", "Olá!"),
        )
        pg_connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, %s, %s)
            """,
            (conv_id, "assistant", "Como posso ajudar?"),
        )

        # Verify messages
        result = pg_connection.execute(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = %s ORDER BY created_at
            """,
            (conv_id,),
        ).fetchall()

        assert len(result) == 2
        assert result[0][0] == "user"
        assert result[0][1] == "Olá!"
        assert result[1][0] == "assistant"

    def test_message_role_constraint(self, pg_connection):
        """role fora de 'user'/'assistant' deve falhar."""
        company_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        pg_connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (%s, %s)",
            (company_id, "Test Corp"),
        )
        pg_connection.execute(
            """
            INSERT INTO conversations (id, user_id, session_id, company_id)
            VALUES (%s, %s, %s, %s)
            """,
            (conv_id, str(uuid.uuid4()), "sess", company_id),
        )

        with pytest.raises(Exception):
            pg_connection.execute(
                """
                INSERT INTO messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (conv_id, "system", "Invalid role"),
            )


class TestMultiTenantIsolation:
    """Testa isolamento multi-tenant."""

    def test_company_data_isolation(self, pg_connection):
        """Company A não deve ver dados de Company B."""
        comp_a = str(uuid.uuid4())
        comp_b = str(uuid.uuid4())

        pg_connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (%s, %s)",
            (comp_a, "Company A"),
        )
        pg_connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (%s, %s)",
            (comp_b, "Company B"),
        )

        # Insert conversations for each company
        conv_a = str(uuid.uuid4())
        conv_b = str(uuid.uuid4())

        pg_connection.execute(
            """
            INSERT INTO conversations (id, user_id, session_id, company_id)
            VALUES (%s, %s, %s, %s)
            """,
            (conv_a, str(uuid.uuid4()), "sess-a", comp_a),
        )
        pg_connection.execute(
            """
            INSERT INTO conversations (id, user_id, session_id, company_id)
            VALUES (%s, %s, %s, %s)
            """,
            (conv_b, str(uuid.uuid4()), "sess-b", comp_b),
        )

        # Verify isolation: query for Company A returns only Company A's data
        result = pg_connection.execute(
            "SELECT id FROM conversations WHERE company_id = %s",
            (comp_a,),
        ).fetchall()

        conv_ids = [str(r[0]) for r in result]
        assert conv_a in conv_ids
        assert conv_b not in conv_ids


class TestBillingTables:
    """Testa tabelas de billing."""

    def test_credit_transaction_type_constraint(self, pg_connection):
        """Apenas tipos válidos devem ser aceitos."""
        with pytest.raises(Exception):
            pg_connection.execute(
                """
                INSERT INTO credit_transactions (company_id, type, amount_brl)
                VALUES (%s, %s, %s)
                """,
                (str(uuid.uuid4()), "invalid_type", 100.00),
            )

    def test_insert_valid_credit_transaction(self, pg_connection):
        company_id = str(uuid.uuid4())
        pg_connection.execute(
            "INSERT INTO companies (id, company_name) VALUES (%s, %s)",
            (company_id, "Corp"),
        )

        pg_connection.execute(
            """
            INSERT INTO credit_transactions (company_id, type, amount_brl, balance_after)
            VALUES (%s, %s, %s, %s)
            """,
            (company_id, "subscription", 399.00, 399.00),
        )

        result = pg_connection.execute(
            "SELECT type, amount_brl FROM credit_transactions WHERE company_id = %s",
            (company_id,),
        ).fetchone()

        assert result[0] == "subscription"
        assert float(result[1]) == 399.00
