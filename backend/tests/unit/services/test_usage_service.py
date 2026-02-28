"""
Unit tests for UsageService — Pricing, cost calculation, caching, and debit logic.
"""

import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services import usage_service as usage_mod
from app.services.usage_service import PRICING_TABLE, UsageService


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset global pricing cache before each test."""
    usage_mod._pricing_cache = {}
    usage_mod._cache_loaded_at = 0
    yield
    usage_mod._pricing_cache = {}
    usage_mod._cache_loaded_at = 0


@pytest.fixture
def usage_service(mock_supabase_client):
    """UsageService com Supabase mockado e cache populado do fallback."""
    mock_supabase_client.client.table.return_value.select.return_value \
        .eq.return_value.execute.return_value = MagicMock(data=[])

    svc = UsageService.__new__(UsageService)
    svc.supabase = mock_supabase_client
    # Popula cache com fallback (sem DB)
    svc._ensure_cache_loaded()
    return svc


# ═══════════════════════════════════════════════════════════════════════════
# PRICING CACHE
# ═══════════════════════════════════════════════════════════════════════════


class TestPricingCache:

    def test_cache_loads_from_database(self, mock_supabase_client):
        """Cache deve carregar pricing do banco."""
        db_pricing = [
            {
                "model_name": "gpt-4o",
                "input_price_per_million": 2.50,
                "output_price_per_million": 10.00,
                "unit": "token",
                "sell_multiplier": 3.00,
                "cache_write_multiplier": None,
                "cache_read_multiplier": None,
                "cached_input_multiplier": None,
            }
        ]
        mock_supabase_client.client.table.return_value.select.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=db_pricing)

        svc = UsageService.__new__(UsageService)
        svc.supabase = mock_supabase_client
        svc._ensure_cache_loaded()

        pricing = usage_mod._pricing_cache.get("gpt-4o")
        assert pricing is not None
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.00
        assert pricing["sell_multiplier"] == 3.00

    def test_cache_falls_back_to_hardcoded_when_db_empty(self, mock_supabase_client):
        """Cache deve usar fallback quando banco retorna vazio."""
        mock_supabase_client.client.table.return_value.select.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[])

        svc = UsageService.__new__(UsageService)
        svc.supabase = mock_supabase_client
        svc._ensure_cache_loaded()

        assert "gpt-4o-mini" in usage_mod._pricing_cache
        assert usage_mod._pricing_cache["gpt-4o-mini"]["input"] == 0.15

    def test_cache_falls_back_on_db_error(self, mock_supabase_client):
        """Cache deve usar fallback quando banco dá erro."""
        mock_supabase_client.client.table.return_value.select.return_value \
            .eq.return_value.execute.side_effect = Exception("DB connection error")

        svc = UsageService.__new__(UsageService)
        svc.supabase = mock_supabase_client
        svc._ensure_cache_loaded()

        assert len(usage_mod._pricing_cache) > 0
        assert "gpt-4o" in usage_mod._pricing_cache

    def test_cache_ttl_avoids_reload(self, usage_service):
        """Cache não deve recarregar se TTL não expirou."""
        usage_mod._cache_loaded_at = time.time()

        usage_service.supabase.client.table.reset_mock()
        usage_service._ensure_cache_loaded()

        usage_service.supabase.client.table.assert_not_called()

    def test_reload_cache_forces_refresh(self, usage_service):
        """reload_cache deve forçar recarga."""
        usage_service.reload_cache()
        usage_service.supabase.client.table.assert_called()


class TestGetPricing:

    def test_returns_pricing_for_known_model(self, usage_service):
        assert usage_service.get_pricing("gpt-4o")["input"] == 2.50
        assert usage_service.get_pricing("gpt-4o")["output"] == 10.00

    def test_returns_fallback_for_unknown_model(self, usage_service):
        pricing = usage_service.get_pricing("nonexistent-model")
        assert pricing["input"] == 0.15  # gpt-4o-mini fallback


# ═══════════════════════════════════════════════════════════════════════════
# COST CALCULATION
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateCost:

    def test_basic_token_cost(self, usage_service):
        """Custo = (input/1M * input_price) + (output/1M * output_price)."""
        cost = usage_service.calculate_cost("gpt-4o", input_tokens=1000, output_tokens=500)
        expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens_zero_cost(self, usage_service):
        assert usage_service.calculate_cost("gpt-4o", 0, 0) == 0.0

    def test_large_token_volume(self, usage_service):
        cost = usage_service.calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        expected = 0.15 + 0.60
        assert abs(cost - expected) < 1e-10

    def test_audio_per_minute_pricing(self, usage_service):
        """Whisper cobra por minuto, não por token."""
        cost = usage_service.calculate_cost("whisper-1", input_tokens=120)  # 2 minutos
        expected = (120 / 60.0) * 0.006
        assert abs(cost - expected) < 1e-10

    def test_anthropic_cache_write_tokens(self, usage_service):
        """Cache write cobra 1.25x do input price."""
        cost = usage_service.calculate_cost(
            "claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=0,
            cache_creation_tokens=500,
        )
        input_price = 3.00
        regular = (500 / 1_000_000) * input_price  # 1000 - 500 cache_create
        cache_write = (500 / 1_000_000) * input_price * 1.25
        expected = regular + cache_write
        assert abs(cost - expected) < 1e-10

    def test_anthropic_cache_read_tokens(self, usage_service):
        """Cache read cobra 0.10x do input price."""
        cost = usage_service.calculate_cost(
            "claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=0,
            cache_read_tokens=400,
        )
        input_price = 3.00
        regular = (600 / 1_000_000) * input_price
        cache_read = (400 / 1_000_000) * input_price * 0.10
        expected = regular + cache_read
        assert abs(cost - expected) < 1e-10

    def test_openai_cached_tokens(self, usage_service):
        """OpenAI cached tokens cobram 0.50x do input."""
        cost = usage_service.calculate_cost(
            "gpt-4o",
            input_tokens=1000,
            output_tokens=0,
            cached_tokens=600,
        )
        input_price = 2.50
        regular = (400 / 1_000_000) * input_price
        cached = (600 / 1_000_000) * input_price * 0.50
        expected = regular + cached
        assert abs(cost - expected) < 1e-10

    def test_negative_regular_tokens_clamped_to_zero(self, usage_service):
        """Se cached > input_tokens, regular não deve ficar negativo."""
        cost = usage_service.calculate_cost(
            "gpt-4o",
            input_tokens=100,
            output_tokens=0,
            cached_tokens=200,  # Mais que input!
        )
        assert cost >= 0


# ═══════════════════════════════════════════════════════════════════════════
# TRACK COST SYNC
# ═══════════════════════════════════════════════════════════════════════════


class TestTrackCostSync:

    def test_logs_usage_to_database(self, usage_service):
        """track_cost_sync deve inserir log no Supabase."""
        usage_service.supabase.client.table.return_value.insert \
            .return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        result = usage_service.track_cost_sync(
            service_type="chat",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            company_id="company-1",
        )

        assert result is True
        usage_service.supabase.client.table.assert_called_with("token_usage_logs")

    def test_returns_false_on_insert_error(self, usage_service):
        usage_service.supabase.client.table.return_value.insert \
            .return_value.execute.side_effect = Exception("DB error")

        result = usage_service.track_cost_sync(
            service_type="chat", model="gpt-4o",
            input_tokens=100, output_tokens=50,
        )
        assert result is False

    def test_returns_false_when_insert_returns_no_data(self, usage_service):
        usage_service.supabase.client.table.return_value.insert \
            .return_value.execute.return_value = MagicMock(data=[])

        result = usage_service.track_cost_sync(
            service_type="chat", model="gpt-4o",
            input_tokens=100, output_tokens=50,
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# CALCULATE AND DEBIT CLIENT
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateAndDebitClient:

    @patch("app.services.usage_service.settings")
    @patch("app.services.billing_service.get_billing_service")
    def test_debits_correct_brl_amount(self, mock_get_bs, mock_settings, usage_service):
        """Fórmula: cost_usd * DOLLAR_RATE * sell_multiplier."""
        mock_settings.DOLLAR_RATE = Decimal("5.50")

        mock_billing = MagicMock()
        mock_get_bs.return_value = mock_billing

        result = usage_service.calculate_and_debit_client(
            company_id="c1",
            agent_id="a1",
            model="gpt-4o-mini",  # input=0.15, sell_multiplier=2.68 (fallback)
            input_tokens=1_000_000,
            output_tokens=0,
        )

        assert result > 0
        mock_billing.debit_credits.assert_called_once()
        call_kwargs = mock_billing.debit_credits.call_args[1]
        assert call_kwargs["company_id"] == "c1"
        assert call_kwargs["agent_id"] == "a1"
        assert call_kwargs["model_name"] == "gpt-4o-mini"
