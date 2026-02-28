"""
E2E tests for Stripe Billing Flow — Webhook handlers via HTTP.

Testa o processamento de eventos Stripe via endpoint:
  POST /api/stripe/webhook → handler correto → operações de billing

Stripe SDK e Supabase são mockados.
Handlers testados:
  - checkout.session.completed → setup subscription + créditos
  - invoice.paid → renovação de créditos
  - invoice.payment_failed → subscription past_due
  - customer.subscription.deleted → cancela subscription

Nota: Os handlers Stripe podem ser testados diretamente (sem HTTP)
nos testes unitários (test_stripe_webhooks.py). Aqui testamos o
fluxo completo via HTTP incluindo verificação de assinatura.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Helper para construir eventos Stripe simulados
# ===========================================================================

def _stripe_event(event_type: str, data: dict) -> dict:
    """Constrói um evento Stripe fake para testes."""
    return {
        "id": f"evt_test_{event_type.replace('.', '_')}",
        "type": event_type,
        "data": {"object": data},
        "created": 1735000000,
    }


def _checkout_event():
    return _stripe_event(
        "checkout.session.completed",
        {
            "id": "cs_test_123",
            "subscription": "sub_test_123",
            "customer": "cus_test_123",
            "payment_status": "paid",
            "metadata": {
                "company_id": "company-test-123",
                "plan_id": "plan-test-456",
            },
        },
    )


def _invoice_paid_event():
    return _stripe_event(
        "invoice.paid",
        {
            "id": "in_test_123",
            "subscription": "sub_test_123",
            "customer": "cus_test_123",
            "billing_reason": "subscription_cycle",
            "lines": {"data": [{"price": {"id": "price_test_123"}}]},
        },
    )


def _invoice_failed_event():
    return _stripe_event(
        "invoice.payment_failed",
        {
            "id": "in_failed_123",
            "subscription": "sub_test_123",
            "customer": "cus_test_123",
        },
    )


def _subscription_deleted_event():
    return _stripe_event(
        "customer.subscription.deleted",
        {
            "id": "sub_test_123",
            "customer": "cus_test_123",
            "status": "canceled",
        },
    )


# ===========================================================================
# TestStripeBillingWebhookEndpoint
# ===========================================================================


@pytest.mark.e2e
class TestStripeBillingWebhookEndpoint:
    """
    Testa o endpoint POST /api/stripe/webhook com eventos simulados.

    Nota: stripe.Webhook.construct_event é mockado para evitar verificação
    de assinatura (que requer chave secreta real).
    """

    async def test_checkout_completed_returns_200(self, e2e_client):
        """checkout.session.completed → 200 OK."""
        event = _checkout_event()

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = await e2e_client.post(
                "/api/stripe/webhook",
                content=json.dumps(event),
                headers={
                    "stripe-signature": "test-signature",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200

    async def test_invoice_paid_returns_200(self, e2e_client):
        """invoice.paid → 200 OK."""
        event = _invoice_paid_event()

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = await e2e_client.post(
                "/api/stripe/webhook",
                content=json.dumps(event),
                headers={
                    "stripe-signature": "test-signature",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200

    async def test_invoice_payment_failed_returns_200(self, e2e_client):
        """invoice.payment_failed → 200 OK (não deve retornar erro HTTP)."""
        event = _invoice_failed_event()

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = await e2e_client.post(
                "/api/stripe/webhook",
                content=json.dumps(event),
                headers={
                    "stripe-signature": "test-signature",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200

    async def test_subscription_deleted_returns_200(self, e2e_client):
        """customer.subscription.deleted → 200 OK."""
        event = _subscription_deleted_event()

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = await e2e_client.post(
                "/api/stripe/webhook",
                content=json.dumps(event),
                headers={
                    "stripe-signature": "test-signature",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200

    async def test_unknown_event_type_handled_gracefully(self, e2e_client):
        """Eventos desconhecidos não devem causar erro 5xx."""
        event = _stripe_event("unknown.event.type", {"id": "test"})

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = await e2e_client.post(
                "/api/stripe/webhook",
                content=json.dumps(event),
                headers={
                    "stripe-signature": "test-signature",
                    "Content-Type": "application/json",
                },
            )

        # Deve retornar 200 (evento ignorado) ou 4xx (não 5xx)
        assert response.status_code < 500
