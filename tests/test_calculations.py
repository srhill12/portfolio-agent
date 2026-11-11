from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.calculations import (
    LotInput,
    combine_positions,
    lot_metrics,
    portfolio_summary,
    round_money,
    round_percent,
)


def test_hand_checkable_combined_googl_and_portfolio() -> None:
    # Hand calculation:
    # GOOGL investment: 10 * 140.00 = 1400.00
    # GOOGL retirement: 5 * 170.00 = 850.00
    # Combined GOOGL: qty 15, cost 2250.00, avg 150.00
    # At 175.00: value 2625.00, gain 375.00, pct 375/2250
    # AAPL: 8 * 190.00 = 1520.00; at 210.00 value 1680.00, gain 160.00
    # Portfolio cost 3770.00, value 4305.00, gain 535.00
    # Weights: GOOGL 2625/4305, AAPL 1680/4305
    investment = uuid4()
    retirement = uuid4()
    lots = [
        LotInput("GOOGL", investment, Decimal("10"), Decimal("140.00")),
        LotInput("GOOGL", retirement, Decimal("5"), Decimal("170.00")),
        LotInput("AAPL", investment, Decimal("8"), Decimal("190.00")),
    ]
    prices = {"GOOGL": Decimal("175.00"), "AAPL": Decimal("210.00")}

    positions = {p.ticker: p for p in combine_positions(lots, prices)}
    googl = positions["GOOGL"]
    assert googl.total_quantity == Decimal("15")
    assert googl.total_cost == Decimal("2250.00")
    assert googl.average_cost == Decimal("150")
    assert googl.market_value == Decimal("2625.00")
    assert googl.unrealized_gain == Decimal("375.00")
    assert googl.unrealized_pct == Decimal("375") / Decimal("2250")

    aapl = positions["AAPL"]
    assert aapl.market_value == Decimal("1680.00")
    assert aapl.unrealized_gain == Decimal("160.00")

    summary = portfolio_summary(lots, prices)
    assert summary.total_cost == Decimal("3770.00")
    assert summary.priced_cost == Decimal("3770.00")
    assert summary.total_market_value == Decimal("4305.00")
    assert summary.total_unrealized_gain == Decimal("535.00")
    assert summary.total_unrealized_pct == Decimal("535") / Decimal("3770")
    assert summary.unpriced_tickers == []
    weights = {w.ticker: w.weight for w in summary.weights}
    assert weights["GOOGL"] == Decimal("2625") / Decimal("4305")
    assert weights["AAPL"] == Decimal("1680") / Decimal("4305")
    assert round_money(summary.total_market_value) == Decimal("4305.00")
    assert round_percent(summary.total_unrealized_pct) == Decimal("14.19")


def test_missing_price_excluded_from_totals() -> None:
    account = uuid4()
    lots = [
        LotInput("GOOGL", account, Decimal("10"), Decimal("140.00")),
        LotInput("AAPL", account, Decimal("8"), Decimal("190.00")),
    ]
    prices = {"GOOGL": Decimal("175.00"), "AAPL": None}

    summary = portfolio_summary(lots, prices)
    assert summary.unpriced_tickers == ["AAPL"]
    assert summary.total_cost == Decimal("2920.00")
    assert summary.priced_cost == Decimal("1400.00")
    assert summary.total_market_value == Decimal("1750.00")
    assert summary.total_unrealized_gain == Decimal("350.00")
    assert all(w.ticker != "AAPL" for w in summary.weights)


def test_zero_cost_basis_pct_is_none() -> None:
    lot = LotInput("ZERO", uuid4(), Decimal("5"), Decimal("0"))
    metrics = lot_metrics(lot, Decimal("10"))
    assert metrics.cost_basis == Decimal("0")
    assert metrics.market_value == Decimal("50")
    assert metrics.unrealized_gain == Decimal("50")
    assert metrics.unrealized_pct is None
