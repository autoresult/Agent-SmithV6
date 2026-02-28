"""
Unit tests for EmailService — SendGrid email alerts.
"""

from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def email_service():
    """EmailService configurado mas sem chamar SendGrid real."""
    from app.services.email_service import EmailService

    svc = EmailService.__new__(EmailService)
    svc.api_key = "SG.test-key"
    svc.from_email = "noreply@test.com"
    svc.configured = True
    return svc


# ═══════════════════════════════════════════════════════════════════════════
# SEND EMAIL
# ═══════════════════════════════════════════════════════════════════════════


class TestSendEmail:

    @patch("app.services.email_service.SendGridAPIClient")
    def test_sends_email_via_sendgrid(self, mock_sg_class, email_service):
        """Deve criar SendGridAPIClient e chamar send()."""
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = MagicMock(status_code=202)
        mock_sg_class.return_value = mock_sg_instance

        result = email_service.send_email(
            to_email="user@example.com",
            subject="Test Subject",
            html_content="<h1>Hello</h1>",
        )

        assert result is True
        mock_sg_class.assert_called_once_with("SG.test-key")
        mock_sg_instance.send.assert_called_once()

    @patch("app.services.email_service.SendGridAPIClient")
    def test_returns_false_on_sendgrid_error(self, mock_sg_class, email_service):
        """Deve retornar False quando SendGrid falha."""
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception("SendGrid error")
        mock_sg_class.return_value = mock_sg_instance

        result = email_service.send_email(
            to_email="user@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result is False

    def test_returns_false_when_not_configured(self, email_service):
        """Deve retornar False quando SendGrid não está configurado."""
        email_service.configured = False

        result = email_service.send_email(
            to_email="user@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# CONSUMPTION ALERTS
# ═══════════════════════════════════════════════════════════════════════════


class TestConsumptionAlert80:

    def test_sends_80_percent_alert(self, email_service):
        """Deve enviar alerta de 80% consumo."""
        email_service.send_email = MagicMock(return_value=True)

        result = email_service.send_consumption_alert_80(
            to_email="admin@corp.com",
            company_name="Test Corp",
            balance_percentage=82.5,
            plan_name="Pro",
        )

        assert result is True
        email_service.send_email.assert_called_once()
        call_kwargs = email_service.send_email.call_args
        assert "80%" in str(call_kwargs)

    def test_includes_company_name_in_body(self, email_service):
        """HTML do email deve conter nome da empresa."""
        email_service.send_email = MagicMock(return_value=True)

        email_service.send_consumption_alert_80(
            to_email="admin@corp.com",
            company_name="Acme Corp",
            balance_percentage=85.0,
            plan_name="Starter",
        )

        html_content = email_service.send_email.call_args[0][2]  # positional arg
        assert "Acme Corp" in html_content


class TestConsumptionAlert100:

    def test_sends_100_percent_alert(self, email_service):
        """Deve enviar alerta de 100% consumo (serviço interrompido)."""
        email_service.send_email = MagicMock(return_value=True)

        result = email_service.send_consumption_alert_100(
            to_email="admin@corp.com",
            company_name="Test Corp",
            plan_name="Pro",
        )

        assert result is True
        email_service.send_email.assert_called_once()

    def test_alert_100_indicates_credits_depleted(self, email_service):
        """Subject deve indicar créditos esgotados."""
        email_service.send_email = MagicMock(return_value=True)

        email_service.send_consumption_alert_100(
            to_email="admin@corp.com",
            company_name="Test Corp",
            plan_name="Pro",
        )

        subject = email_service.send_email.call_args[0][1]  # positional arg
        assert "Esgotados" in subject or "esgotados" in subject.lower()
