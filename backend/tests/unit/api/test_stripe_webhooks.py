"""
Unit tests for Stripe Webhook handlers — Event routing, signature, and handler logic.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Handlers são funções standalone, não importam o router diretamente
from app.api.stripe_webhooks import (
    handle_checkout_completed,
    handle_invoice_paid,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def billing_service():
    """Mock do BillingService para os handlers."""
    svc = MagicMock()
    svc.setup_subscription.return_value = True
    svc.process_invoice_payment.return_value = True
    svc.mark_subscription_past_due.return_value = True
    svc.cancel_subscription.return_value = True
    svc.is_payment_processed.return_value = False
    svc.get_subscription_by_stripe_id.return_value = {
        "company_id": "comp-1",
        "plan_id": "plan-starter",
    }
    return svc


def _make_event(event_type: str, data_object: dict) -> dict:
    """Helper para criar evento Stripe mock."""
    return {
        "type": event_type,
        "data": {"object": data_object},
    }


# ═══════════════════════════════════════════════════════════════════════════
# CHECKOUT.SESSION.COMPLETED
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleCheckoutCompleted:

    @pytest.fixture
    def checkout_event(self):
        return _make_event("checkout.session.completed", {
            "metadata": {"company_id": "comp-1", "plan_id": "starter"},
            "subscription": "sub_12345",
            "customer": "cus_12345",
        })

    @patch("app.api.stripe_webhooks.stripe")
    async def test_creates_subscription_record(self, mock_stripe, checkout_event, billing_service):
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"current_period_start": 1700000000, "current_period_end": 1702600000}]},
        }

        await handle_checkout_completed(checkout_event, billing_service)

        billing_service.setup_subscription.assert_called_once()
        call_kwargs = billing_service.setup_subscription.call_args[1]
        assert call_kwargs["company_id"] == "comp-1"
        assert call_kwargs["plan_id"] == "starter"
        assert call_kwargs["stripe_subscription_id"] == "sub_12345"

    @patch("app.api.stripe_webhooks.stripe")
    async def test_missing_metadata_raises(self, mock_stripe, billing_service):
        event = _make_event("checkout.session.completed", {
            "metadata": {},
            "subscription": "sub_1",
        })

        with pytest.raises(ValueError, match="Missing company_id"):
            await handle_checkout_completed(event, billing_service)

    @patch("app.api.stripe_webhooks.stripe")
    async def test_no_subscription_skips_silently(self, mock_stripe, billing_service):
        event = _make_event("checkout.session.completed", {
            "metadata": {"company_id": "c1", "plan_id": "p1"},
            "subscription": None,
        })

        await handle_checkout_completed(event, billing_service)
        billing_service.setup_subscription.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# INVOICE.PAID
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleInvoicePaid:

    @pytest.fixture
    def invoice_event(self):
        return _make_event("invoice.paid", {
            "id": "inv_12345",
            "subscription": "sub_12345",
            "billing_reason": "subscription_cycle",
            "amount_paid": 39900,  # R$399,00 em centavos
        })

    @patch("app.api.stripe_webhooks.stripe")
    async def test_processes_subscription_cycle(self, mock_stripe, invoice_event, billing_service):
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"current_period_start": 1700000000, "current_period_end": 1702600000}]},
        }

        await handle_invoice_paid(invoice_event, billing_service)

        billing_service.process_invoice_payment.assert_called_once()
        call_kwargs = billing_service.process_invoice_payment.call_args[1]
        assert call_kwargs["stripe_payment_id"] == "inv_12345"
        assert call_kwargs["amount_paid"] == Decimal("399.00")
        assert call_kwargs["billing_reason"] == "subscription_cycle"

    @patch("app.api.stripe_webhooks.stripe")
    async def test_skips_already_processed_invoice(self, mock_stripe, invoice_event, billing_service):
        billing_service.is_payment_processed.return_value = True
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"current_period_start": 1700000000, "current_period_end": 1702600000}]},
        }

        await handle_invoice_paid(invoice_event, billing_service)

        billing_service.process_invoice_payment.assert_not_called()

    async def test_skips_non_subscription_invoice(self, billing_service):
        event = _make_event("invoice.paid", {
            "id": "inv_1",
            "subscription": None,
            "billing_reason": "manual",
        })

        await handle_invoice_paid(event, billing_service)
        billing_service.process_invoice_payment.assert_not_called()

    async def test_skips_unhandled_billing_reason(self, billing_service):
        event = _make_event("invoice.paid", {
            "id": "inv_1",
            "subscription": "sub_1",
            "billing_reason": "upcoming",
        })

        await handle_invoice_paid(event, billing_service)
        billing_service.process_invoice_payment.assert_not_called()

    @patch("app.api.stripe_webhooks.stripe")
    async def test_extracts_subscription_from_new_api(self, mock_stripe, billing_service):
        """Stripe API 2025+: subscription em parent.subscription_details."""
        event = _make_event("invoice.paid", {
            "id": "inv_1",
            "subscription": None,
            "billing_reason": "subscription_create",
            "amount_paid": 10000,
            "parent": {
                "type": "subscription_details",
                "subscription_details": {"subscription": "sub_new_api"},
            },
        })
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"current_period_start": 1700000000, "current_period_end": 1702600000}]},
        }

        await handle_invoice_paid(event, billing_service)
        billing_service.process_invoice_payment.assert_called_once()

    @patch("app.api.stripe_webhooks.stripe")
    async def test_creates_subscription_if_not_exists(self, mock_stripe, billing_service):
        """Se invoice.paid chega antes de checkout, cria subscription."""
        billing_service.get_subscription_by_stripe_id.return_value = None
        mock_stripe.Subscription.retrieve.return_value = {
            "metadata": {"company_id": "comp-1", "plan_id": "starter"},
            "customer": "cus_1",
            "items": {"data": [{"current_period_start": 1700000000, "current_period_end": 1702600000}]},
        }

        event = _make_event("invoice.paid", {
            "id": "inv_1",
            "subscription": "sub_1",
            "billing_reason": "subscription_create",
            "amount_paid": 39900,
        })

        await handle_invoice_paid(event, billing_service)

        billing_service.setup_subscription.assert_called_once()
        billing_service.process_invoice_payment.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# INVOICE.PAYMENT_FAILED
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleInvoicePaymentFailed:

    async def test_marks_subscription_past_due(self, billing_service):
        event = _make_event("invoice.payment_failed", {
            "id": "inv_fail_1",
            "subscription": "sub_12345",
            "billing_reason": "subscription_cycle",
            "customer_email": "user@example.com",
        })

        await handle_invoice_payment_failed(event, billing_service)
        billing_service.mark_subscription_past_due.assert_called_once_with("sub_12345")

    async def test_extracts_subscription_from_new_api_format(self, billing_service):
        event = _make_event("invoice.payment_failed", {
            "id": "inv_fail_2",
            "subscription": None,
            "billing_reason": "subscription_cycle",
            "customer_email": "user@example.com",
            "parent": {
                "type": "subscription_details",
                "subscription_details": {"subscription": "sub_new"},
            },
        })

        await handle_invoice_payment_failed(event, billing_service)
        billing_service.mark_subscription_past_due.assert_called_once_with("sub_new")

    async def test_skips_when_no_subscription_found(self, billing_service):
        event = _make_event("invoice.payment_failed", {
            "id": "inv_fail_3",
            "subscription": None,
            "billing_reason": "manual",
            "customer_email": "user@example.com",
        })

        await handle_invoice_payment_failed(event, billing_service)
        billing_service.mark_subscription_past_due.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMER.SUBSCRIPTION.DELETED
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleSubscriptionDeleted:

    async def test_cancels_subscription(self, billing_service):
        event = _make_event("customer.subscription.deleted", {
            "id": "sub_12345",
        })

        await handle_subscription_deleted(event, billing_service)
        billing_service.cancel_subscription.assert_called_once_with("sub_12345")

    async def test_skips_when_no_id(self, billing_service):
        event = _make_event("customer.subscription.deleted", {
            "id": None,
        })

        await handle_subscription_deleted(event, billing_service)
        billing_service.cancel_subscription.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMER.SUBSCRIPTION.UPDATED
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleSubscriptionUpdated:

    async def test_updates_cancel_at_when_scheduled(self, billing_service):
        event = _make_event("customer.subscription.updated", {
            "id": "sub_12345",
            "cancel_at": 1700000000,
            "items": {"data": [{"price": {"id": "price_abc"}}]},
        })

        await handle_subscription_updated(event, billing_service)

        billing_service.update_subscription_cancel_at.assert_called_once_with(
            stripe_subscription_id="sub_12345",
            cancel_at=1700000000,
        )

    async def test_clears_cancel_at_when_reverted(self, billing_service):
        event = _make_event("customer.subscription.updated", {
            "id": "sub_12345",
            "cancel_at": None,
            "items": {"data": [{"price": {"id": "price_abc"}}]},
        })

        await handle_subscription_updated(event, billing_service)

        billing_service.update_subscription_cancel_at.assert_called_once_with(
            stripe_subscription_id="sub_12345",
            cancel_at=None,
        )

    async def test_updates_plan_by_price_id(self, billing_service):
        event = _make_event("customer.subscription.updated", {
            "id": "sub_12345",
            "cancel_at": None,
            "items": {"data": [{"price": {"id": "price_new_plan"}}]},
        })

        await handle_subscription_updated(event, billing_service)

        billing_service.update_subscription_plan_by_price.assert_called_once_with(
            stripe_subscription_id="sub_12345",
            stripe_price_id="price_new_plan",
        )

    async def test_skips_plan_update_when_no_items(self, billing_service):
        event = _make_event("customer.subscription.updated", {
            "id": "sub_12345",
            "cancel_at": None,
            "items": {"data": []},
        })

        await handle_subscription_updated(event, billing_service)

        billing_service.update_subscription_plan_by_price.assert_not_called()
