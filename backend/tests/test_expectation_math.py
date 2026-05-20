"""Unit test della parte numerica dell'expectation engine (earnings surprise)."""

import pytest

from app.agents.expectation import ExpectationEngine


@pytest.mark.parametrize(
    ("estimate", "actual", "expected_direction", "expected_magnitude"),
    [
        (1.00, 1.05, "positive", "medium"),    # +5% beat
        (1.00, 1.20, "positive", "high"),      # +20% beat
        (1.00, 0.95, "negative", "medium"),    # -5% miss
        (1.00, 0.80, "negative", "high"),      # -20% miss
        (1.00, 1.01, "positive", "low"),       # +1% in line
        (1.00, 1.00, "neutral", "low"),
        (None, 1.00, "uncertain", "low"),
        (1.00, None, "uncertain", "low"),
        (0.0, 1.00, "uncertain", "low"),
    ],
)
def test_earnings_surprise(estimate, actual, expected_direction, expected_magnitude):
    direction, magnitude, zscore = ExpectationEngine._earnings_surprise(estimate, actual)
    assert direction == expected_direction
    assert magnitude == expected_magnitude
    if estimate and actual is not None and estimate != 0:
        assert zscore is not None


def test_earnings_surprise_zscore_sign():
    """Beat → z > 0, miss → z < 0."""
    _, _, z_beat = ExpectationEngine._earnings_surprise(1.0, 1.10)
    _, _, z_miss = ExpectationEngine._earnings_surprise(1.0, 0.90)
    assert z_beat is not None and z_beat > 0
    assert z_miss is not None and z_miss < 0
