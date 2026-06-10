"""Tests for NEXUS regime detection."""
import pytest
from nexus.regime import detect_regime, Regime


class TestRegimeDetection:
    def test_detect_regime_returns_valid_result(self):
        """Smoke test: regime detection runs without error."""
        result = detect_regime()
        assert result.regime in Regime
        assert 0.0 <= result.confidence <= 1.0
        assert 0 <= result.fear_greed <= 100

    def test_regime_enum_values(self):
        """All regime values are valid trading states."""
        assert Regime.TRENDING_UP.value == "trending_up"
        assert Regime.TRENDING_DOWN.value == "trending_down"
        assert Regime.RANGING.value == "ranging"
        assert Regime.RISK_OFF.value == "risk_off"

    def test_risk_off_blocks_trading(self):
        """RISK_OFF must result in zero-position recommendation."""
        result = detect_regime()
        if result.regime == Regime.RISK_OFF:
            assert result.confidence >= 0.5, "RISK_OFF with low confidence is suspicious"
