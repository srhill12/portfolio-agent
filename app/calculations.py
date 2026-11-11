"""Pure portfolio calculation helpers (no I/O).

All money and quantity math uses Decimal. Rounding is only for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID


@dataclass(frozen=True)
class LotInput:
    ticker: str
    account_id: UUID
    quantity: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class LotMetrics:
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    unrealized_pct: Decimal | None


@dataclass(frozen=True)
class CombinedPosition:
    ticker: str
    total_quantity: Decimal
    total_cost: Decimal
    average_cost: Decimal
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    unrealized_pct: Decimal | None


@dataclass(frozen=True)
class PositionWeight:
    ticker: str
    weight: Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    total_cost: Decimal
    priced_cost: Decimal
    total_market_value: Decimal
    total_unrealized_gain: Decimal | None
    total_unrealized_pct: Decimal | None
    weights: list[PositionWeight]
    unpriced_tickers: list[str]


_MONEY_QUANT = Decimal("0.01")
_PCT_QUANT = Decimal("0.01")
_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def lot_metrics(lot: LotInput, price: Decimal | None) -> LotMetrics:
    cost_basis = lot.quantity * lot.unit_cost
    if price is None:
        return LotMetrics(
            cost_basis=cost_basis,
            market_value=None,
            unrealized_gain=None,
            unrealized_pct=None,
        )
    market_value = lot.quantity * price
    unrealized_gain = market_value - cost_basis
    unrealized_pct = None if cost_basis == _ZERO else unrealized_gain / cost_basis
    return LotMetrics(
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_gain=unrealized_gain,
        unrealized_pct=unrealized_pct,
    )


def combine_positions(
    lots: list[LotInput],
    prices: dict[str, Decimal | None],
) -> list[CombinedPosition]:
    by_ticker: dict[str, list[LotInput]] = {}
    for lot in lots:
        by_ticker.setdefault(lot.ticker, []).append(lot)

    positions: list[CombinedPosition] = []
    for ticker in sorted(by_ticker):
        group = by_ticker[ticker]
        total_quantity = sum((lot.quantity for lot in group), _ZERO)
        total_cost = sum((lot.quantity * lot.unit_cost for lot in group), _ZERO)
        average_cost = total_cost / total_quantity
        price = prices.get(ticker)
        if price is None:
            positions.append(
                CombinedPosition(
                    ticker=ticker,
                    total_quantity=total_quantity,
                    total_cost=total_cost,
                    average_cost=average_cost,
                    market_value=None,
                    unrealized_gain=None,
                    unrealized_pct=None,
                )
            )
            continue
        market_value = total_quantity * price
        unrealized_gain = market_value - total_cost
        unrealized_pct = None if total_cost == _ZERO else unrealized_gain / total_cost
        positions.append(
            CombinedPosition(
                ticker=ticker,
                total_quantity=total_quantity,
                total_cost=total_cost,
                average_cost=average_cost,
                market_value=market_value,
                unrealized_gain=unrealized_gain,
                unrealized_pct=unrealized_pct,
            )
        )
    return positions


def portfolio_summary(
    lots: list[LotInput],
    prices: dict[str, Decimal | None],
) -> PortfolioSummary:
    positions = combine_positions(lots, prices)
    unpriced = [p.ticker for p in positions if p.market_value is None]
    priced = [p for p in positions if p.market_value is not None]

    total_cost = sum((p.total_cost for p in positions), _ZERO)
    priced_cost = sum((p.total_cost for p in priced), _ZERO)
    total_market_value = sum((p.market_value for p in priced), _ZERO)  # type: ignore[misc]

    if not priced:
        return PortfolioSummary(
            total_cost=total_cost,
            priced_cost=priced_cost,
            total_market_value=_ZERO,
            total_unrealized_gain=None,
            total_unrealized_pct=None,
            weights=[],
            unpriced_tickers=unpriced,
        )

    total_unrealized_gain = total_market_value - priced_cost
    total_unrealized_pct = (
        None if priced_cost == _ZERO else total_unrealized_gain / priced_cost
    )
    weights: list[PositionWeight] = []
    if total_market_value != _ZERO:
        for position in priced:
            assert position.market_value is not None
            weights.append(
                PositionWeight(
                    ticker=position.ticker,
                    weight=position.market_value / total_market_value,
                )
            )
    return PortfolioSummary(
        total_cost=total_cost,
        priced_cost=priced_cost,
        total_market_value=total_market_value,
        total_unrealized_gain=total_unrealized_gain,
        total_unrealized_pct=total_unrealized_pct,
        weights=weights,
        unpriced_tickers=unpriced,
    )


def round_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def round_percent(value: Decimal) -> Decimal:
    """Convert a fraction to percentage points rounded to 2 places (0.141909 -> 14.19)."""
    return (value * _HUNDRED).quantize(_PCT_QUANT, rounding=ROUND_HALF_UP)


def plain_decimal(value: Decimal) -> str:
    """Strip trailing zeros for form prefills (no thousands separators)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_quantity(value: Decimal) -> str:
    """Strip trailing zeros and add thousands separators."""
    text = plain_decimal(value)
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".", 1)
        whole = f"{int(whole):,}"
        result = f"{whole}.{frac}"
    else:
        result = f"{int(text):,}"
    return f"-{result}" if negative else result


def format_money(value: Decimal) -> str:
    rounded = round_money(value)
    return f"${rounded:,.2f}"


def format_percent(fraction: Decimal) -> str:
    return f"{round_percent(fraction)}%"
