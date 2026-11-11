from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class QuoteResult:
    price: Decimal
    as_of: datetime
    source: str = "finnhub"


class QuoteClient(Protocol):
    """Fetch a live quote. Return None when the symbol is unknown."""

    def fetch_quote(self, ticker: str) -> QuoteResult | None: ...
