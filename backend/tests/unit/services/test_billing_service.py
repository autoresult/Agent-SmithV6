"""
Unit tests for BillingService — Stripe subscription lifecycle.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def billing_service(mock_supabase_client):
    """BillingService com Supabase mockado.

    BillingService herda de BillingCore que usa self.client (Supabase raw client).
    """
    from app.services.billing_service import BillingService

    svc = BillingService.__new__(BillingService)
    svc.client = mock_supabase_client.client
    return svc


# ═══════════════════════════════════════════════════════════════════════════
# SETUP SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════


class TestSetupSubscription:

    def test_creates_new_subscription(self, billing_service):
        c = billing_service.client
        # select().eq().limit().execute() => no existing
        c.table.return_value.select.return_value.eq.return_value \
            .limit.return_value.execute.return_value = MagicMock(data=[])
        # insert().execute()
        c.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        # update().eq().execute() (company update)
        c.table.return_value.update.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": 1}])

        result = billing_service.setup_subscription(
            company_id="comp-1", plan_id="starter",
            stripe_subscription_id="sub_123", stripe_customer_id="cus_123",
            current_period_start=datetime(2025, 1, 1),
            current_period_end=datetime(2025, 2, 1),
        )
        assert result is True

    def test_returns_false_on_error(self, billing_service):
        billing_service.client.table.return_value.select.return_value \
            .eq.return_value.limit.return_value.execute.side_effect = Exception("err")

        result = billing_service.setup_subscription(
            company_id="c", plan_id="p",
            stripe_subscription_id="s", stripe_customer_id="c",
            current_period_start=datetime.now(), current_period_end=datetime.now(),
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# GET SUBSCRIPTION BY STRIPE ID
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSubscriptionByStripeId:

    def test_returns_subscription_data(self, billing_service):
        # Uses: .select().eq().single().execute()
        billing_service.client.table.return_value.select.return_value \
            .eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"company_id": "comp-1", "plan_id": "pro"}
            )

        result = billing_service.get_subscription_by_stripe_id("sub_123")
        assert result is not None
        assert result["company_id"] == "comp-1"

    def test_returns_none_when_not_found(self, billing_service):
        # single() raises exception when no row found
        billing_service.client.table.return_value.select.return_value \
            .eq.return_value.single.return_value.execute.side_effect = Exception("No rows")

        result = billing_service.get_subscription_by_stripe_id("sub_nonexistent")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# MARK SUBSCRIPTION PAST DUE
# ═══════════════════════════════════════════════════════════════════════════


class TestMarkSubscriptionPastDue:

    def test_updates_status_to_past_due(self, billing_service):
        c = billing_service.client

        # select and update both call client.table("subscriptions")
        # Use separate mock objects for each call
        select_mock = MagicMock()
        select_result = MagicMock()
        select_result.data = [{"id": "sub-1", "company_id": "comp-1", "status": "active"}]
        select_mock.select.return_value.eq.return_value.execute.return_value = select_result

        update_mock = MagicMock()
        update_result = MagicMock()
        update_result.data = [{"status": "past_due"}]
        update_mock.update.return_value.eq.return_value.execute.return_value = update_result

        c.table.side_effect = [select_mock, update_mock]

        result = billing_service.mark_subscription_past_due("sub_123")
        assert result is True

    def test_returns_false_when_subscription_not_found(self, billing_service):
        billing_service.client.table.return_value.select.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[])

        result = billing_service.mark_subscription_past_due("sub_nonexistent")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# PROCESS INVOICE PAYMENT
# ═══════════════════════════════════════════════════════════════════════════


class TestProcessInvoicePayment:

    def test_adds_credits_on_subscription_create(self, billing_service):
        c = billing_service.client
        billing_service.is_payment_processed = MagicMock(return_value=False)
        billing_service.add_credits = MagicMock(return_value=True)

        # select().eq().single().execute() => subscription found
        c.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(
                data={"id": "sub-1", "company_id": "comp-1", "plan_id": "pro", "plans": {"name": "Pro"}}
            )
        # update().eq().execute() => period update
        c.table.return_value.update.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": 1}])

        result = billing_service.process_invoice_payment(
            stripe_subscription_id="sub_123",
            stripe_payment_id="inv_123",
            amount_paid=Decimal("399.00"),
            billing_reason="subscription_create",
            current_period_start=datetime(2025, 2, 1),
            current_period_end=datetime(2025, 3, 1),
        )

        assert result is True
        billing_service.add_credits.assert_called_once()

    def test_resets_credits_on_subscription_cycle(self, billing_service):
        c = billing_service.client
        billing_service.is_payment_processed = MagicMock(return_value=False)
        billing_service.reset_credits = MagicMock(return_value=True)

        c.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(
                data={"id": "sub-1", "company_id": "comp-1", "plan_id": "pro", "plans": {"name": "Pro"}}
            )
        c.table.return_value.update.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": 1}])

        result = billing_service.process_invoice_payment(
            stripe_subscription_id="sub_123",
            stripe_payment_id="inv_456",
            amount_paid=Decimal("399.00"),
            billing_reason="subscription_cycle",
            current_period_start=datetime(2025, 3, 1),
            current_period_end=datetime(2025, 4, 1),
        )

        assert result is True
        billing_service.reset_credits.assert_called_once()

    def test_skips_when_already_processed(self, billing_service):
        billing_service.is_payment_processed = MagicMock(return_value=True)

        result = billing_service.process_invoice_payment(
            stripe_subscription_id="sub_1",
            stripe_payment_id="inv_dup",
            amount_paid=Decimal("399.00"),
            billing_reason="subscription_cycle",
            current_period_start=datetime.now(),
            current_period_end=datetime.now(),
        )

        assert result is True  # returns True (already processed)


# ═══════════════════════════════════════════════════════════════════════════
# CANCEL SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════


class TestCancelSubscription:

    def test_cancels_and_zeroes_credits(self, billing_service):
        c = billing_service.client
        c.table.return_value.select.return_value.eq.return_value \
            .single.return_value.execute.return_value = MagicMock(
                data={"company_id": "comp-1", "plan_id": "pro"}
            )
        c.table.return_value.update.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": 1}])

        billing_service._send_cancellation_email = MagicMock()

        result = billing_service.cancel_subscription("sub_123")
        assert result is True

    def test_returns_false_when_subscription_not_found(self, billing_service):
        billing_service.client.table.return_value.select.return_value \
            .eq.return_value.single.return_value.execute.side_effect = Exception("Not found")

        result = billing_service.cancel_subscription("sub_nonexistent")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# UPDATE CANCEL_AT
# ═══════════════════════════════════════════════════════════════════════════


class TestUpdateSubscriptionCancelAt:

    def test_sets_cancel_at_timestamp(self, billing_service):
        billing_service.client.table.return_value.update.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        result = billing_service.update_subscription_cancel_at("sub_1", cancel_at=1700000000)
        assert result is True

    def test_clears_cancel_at(self, billing_service):
        billing_service.client.table.return_value.update.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        result = billing_service.update_subscription_cancel_at("sub_1", cancel_at=None)
        assert result is True
