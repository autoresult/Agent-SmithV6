"""
Unit tests for BillingCore — Core billing logic.

Testa lógica financeira PURA: créditos, débitos, alertas, status de subscription.
O Supabase client é completamente mockado.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Precisamos importar BillingCore, mas ele importa 'supabase'
# que está mockado no unit/conftest.py. Importamos após o mock.
# ---------------------------------------------------------------------------
from app.workers.billing_core import BillingCore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Mock do Supabase Client com chaining completo."""
    client = MagicMock()
    table = MagicMock()

    # Configura chaining: client.table("x").select("y").eq("z")...
    client.table.return_value = table
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.upsert.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.neq.return_value = table
    table.in_.return_value = table
    table.gte.return_value = table
    table.limit.return_value = table
    table.order.return_value = table
    table.single.return_value = table
    table.maybe_single.return_value = table

    return client


@pytest.fixture
def billing(mock_client):
    """BillingCore com mock client."""
    return BillingCore(mock_client)


# ═══════════════════════════════════════════════════════════════════════════
# GET BALANCE
# ═══════════════════════════════════════════════════════════════════════════


class TestGetCompanyBalance:

    def test_returns_balance_from_db(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(
            data={"balance_brl": "150.5000"}
        )
        balance = billing.get_company_balance("company-1")
        assert balance == Decimal("150.5000")

    def test_returns_zero_when_no_data(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(data=None)
        balance = billing.get_company_balance("company-1")
        assert balance == Decimal("0")

    def test_returns_zero_on_exception(self, billing, mock_client):
        mock_client.table.side_effect = Exception("DB error")
        balance = billing.get_company_balance("company-1")
        assert balance == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# ADD CREDITS
# ═══════════════════════════════════════════════════════════════════════════


class TestAddCredits:

    def test_add_credits_upserts_and_records_transaction(self, billing, mock_client):
        # Mock get_company_balance
        mock_client.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(
            data={"balance_brl": "100.0000"}
        )

        result = billing.add_credits(
            company_id="company-1",
            amount_brl=Decimal("50.00"),
            transaction_type="subscription",
            description="Monthly subscription",
            stripe_payment_id="pi_test123"
        )

        assert result is True
        # Verifica que upsert e insert foram chamados
        assert mock_client.table.call_count >= 2

    def test_add_credits_returns_false_on_error(self, billing, mock_client):
        mock_client.table.side_effect = Exception("DB error")
        result = billing.add_credits(
            company_id="company-1",
            amount_brl=Decimal("50.00"),
            transaction_type="subscription",
            description="Test"
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# RESET CREDITS
# ═══════════════════════════════════════════════════════════════════════════


class TestResetCredits:

    def test_reset_credits_sets_exact_balance(self, billing, mock_client):
        result = billing.reset_credits(
            company_id="company-1",
            amount_brl=Decimal("399.00"),
            description="Renewal",
            stripe_payment_id="pi_renew"
        )
        assert result is True

    def test_reset_credits_returns_false_on_error(self, billing, mock_client):
        mock_client.table.side_effect = Exception("DB error")
        result = billing.reset_credits(
            company_id="company-1",
            amount_brl=Decimal("399.00"),
            description="Renewal"
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# DEBIT CREDITS
# ═══════════════════════════════════════════════════════════════════════════


class TestDebitCredits:

    def test_debit_credits_calls_rpc(self, billing, mock_client):
        mock_client.rpc.return_value.execute.return_value = MagicMock(data="149.50")

        result = billing.debit_credits(
            company_id="company-1",
            agent_id="agent-1",
            amount_brl=Decimal("0.0050"),
            model_name="gpt-4o-mini",
            tokens_input=100,
            tokens_output=200,
            check_alerts=False
        )
        assert result is True
        mock_client.rpc.assert_called_once_with(
            'debit_company_balance',
            {'p_company_id': 'company-1', 'p_amount': 0.005}
        )

    def test_debit_credits_records_transaction_with_agent_id(self, billing, mock_client):
        mock_client.rpc.return_value.execute.return_value = MagicMock(data="100")

        billing.debit_credits(
            company_id="company-1",
            agent_id="agent-1",
            amount_brl=Decimal("0.01"),
            model_name="gpt-4o",
            tokens_input=50,
            tokens_output=100,
            check_alerts=False
        )

        # Verifica que insert foi chamado com agent_id
        insert_call = mock_client.table.return_value.insert
        assert insert_call.called
        inserted_data = insert_call.call_args[0][0]
        assert inserted_data["agent_id"] == "agent-1"
        assert inserted_data["type"] == "consumption"
        assert inserted_data["amount_brl"] == -0.01

    def test_debit_credits_without_agent_id(self, billing, mock_client):
        mock_client.rpc.return_value.execute.return_value = MagicMock(data="100")

        billing.debit_credits(
            company_id="company-1",
            agent_id=None,
            amount_brl=Decimal("0.01"),
            model_name="gpt-4o",
            tokens_input=50,
            tokens_output=100,
            check_alerts=False
        )

        inserted_data = mock_client.table.return_value.insert.call_args[0][0]
        assert "agent_id" not in inserted_data

    def test_debit_credits_returns_false_on_error(self, billing, mock_client):
        mock_client.rpc.side_effect = Exception("RPC error")
        result = billing.debit_credits(
            company_id="company-1",
            agent_id=None,
            amount_brl=Decimal("0.01"),
            model_name="gpt-4o",
            tokens_input=50,
            tokens_output=100,
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION STATUS
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscriptionStatus:

    def test_blocked_when_company_suspended(self, billing, mock_client):
        # Primeiro call: companies table
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.single.return_value.execute.return_value = MagicMock(
            data={"status": "suspended"}
        )
        assert billing.is_subscription_blocked("company-1") is True

    def test_blocked_when_subscription_past_due(self, billing, mock_client):
        responses = [
            MagicMock(data={"status": "active"}),  # companies
            MagicMock(data={"status": "past_due"}),  # subscriptions
        ]
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.single.return_value.execute.side_effect = responses
        assert billing.is_subscription_blocked("company-1") is True

    def test_blocked_when_subscription_cancelled(self, billing, mock_client):
        responses = [
            MagicMock(data={"status": "active"}),
            MagicMock(data={"status": "cancelled"}),
        ]
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.single.return_value.execute.side_effect = responses
        assert billing.is_subscription_blocked("company-1") is True

    def test_not_blocked_when_active(self, billing, mock_client):
        responses = [
            MagicMock(data={"status": "active"}),  # companies
            MagicMock(data={"status": "active"}),  # subscriptions
        ]
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.single.return_value.execute.side_effect = responses
        assert billing.is_subscription_blocked("company-1") is False

    def test_not_blocked_without_subscription(self, billing, mock_client):
        responses = [
            MagicMock(data={"status": "active"}),
            MagicMock(data=None),  # No subscription
        ]
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.single.return_value.execute.side_effect = responses
        assert billing.is_subscription_blocked("company-1") is False

    def test_fail_open_on_error(self, billing, mock_client):
        """Em caso de erro, NÃO bloqueia (fail open)."""
        mock_client.table.side_effect = Exception("DB error")
        assert billing.is_subscription_blocked("company-1") is False


# ═══════════════════════════════════════════════════════════════════════════
# HAS SUFFICIENT BALANCE
# ═══════════════════════════════════════════════════════════════════════════


class TestHasSufficientBalance:

    def test_sufficient_balance(self, billing, mock_client):
        # Mock is_subscription_blocked → False
        with patch.object(billing, 'is_subscription_blocked', return_value=False):
            with patch.object(billing, 'get_company_balance', return_value=Decimal("100.00")):
                assert billing.has_sufficient_balance("company-1") is True

    def test_insufficient_balance(self, billing, mock_client):
        with patch.object(billing, 'is_subscription_blocked', return_value=False):
            with patch.object(billing, 'get_company_balance', return_value=Decimal("0.00")):
                assert billing.has_sufficient_balance("company-1", Decimal("0.01")) is False

    def test_blocked_subscription_returns_false(self, billing, mock_client):
        with patch.object(billing, 'is_subscription_blocked', return_value=True):
            assert billing.has_sufficient_balance("company-1") is False


# ═══════════════════════════════════════════════════════════════════════════
# PAYMENT IDEMPOTENCY
# ═══════════════════════════════════════════════════════════════════════════


class TestPaymentIdempotency:

    def test_payment_already_processed(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "tx-1"}]
        )
        assert billing.is_payment_processed("pi_test123") is True

    def test_payment_not_processed(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.execute.return_value = MagicMock(data=[])
        assert billing.is_payment_processed("pi_test123") is False

    def test_error_returns_false(self, billing, mock_client):
        mock_client.table.side_effect = Exception("DB error")
        assert billing.is_payment_processed("pi_test123") is False


# ═══════════════════════════════════════════════════════════════════════════
# CREDITS DISPLAY
# ═══════════════════════════════════════════════════════════════════════════


class TestCreditsDisplay:

    def test_calculates_proportional_credits(self, billing, mock_client):
        with patch.object(billing, 'get_company_balance', return_value=Decimal("200.00")):
            mock_client.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={
                    "plan_id": "plan-1",
                    "plans": {
                        "price_brl": "400.00",
                        "display_credits": 10000,
                        "name": "Pro"
                    }
                }
            )
            result = billing.get_company_credits_display("company-1")
            assert result["credits"] == 5000  # 50% of 10000
            assert result["percentage"] == 50.0
            assert result["plan_name"] == "Pro"

    def test_returns_zeros_when_no_plan(self, billing, mock_client):
        with patch.object(billing, 'get_company_balance', return_value=Decimal("0")):
            mock_client.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=None
            )
            result = billing.get_company_credits_display("company-1")
            assert result["credits"] == 0
            assert result["percentage"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# OWNER EMAIL
# ═══════════════════════════════════════════════════════════════════════════


class TestGetOwnerEmail:

    def test_finds_owner_by_is_owner(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"email": "owner@test.com"}]
        )
        assert billing.get_owner_email("company-1") == "owner@test.com"

    def test_returns_none_when_no_owner(self, billing, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        # Fallback also returns empty
        mock_client.table.return_value.select.return_value.eq.return_value \
            .in_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        assert billing.get_owner_email("company-1") is None
