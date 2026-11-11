"""Market-data provider clients and protocols."""

from app.market_data.protocol import QuoteClient, QuoteResult

__all__ = ["QuoteClient", "QuoteResult"]
