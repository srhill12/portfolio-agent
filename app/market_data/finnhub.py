"""Thin Finnhub /quote client (free-plan endpoint only)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from app.market_data.protocol import QuoteResult
from app.services.errors import ProviderUnavailable

logger = logging.getLogger(__name__)

_QUOTE_URL = "https://finnhub.io/api/v1/quote"
_TIMEOUT = httpx.Timeout(5.0)
_RETRY_WAIT_SECONDS = 1.0


class FinnhubClient:
    def __init__(self, api_key: str, *, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=_TIMEOUT)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FinnhubClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_quote(self, ticker: str) -> QuoteResult | None:
        symbol = (ticker or "").strip().upper()
        if not symbol:
            return None

        response = self._request(symbol)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderUnavailable("Finnhub returned a non-object quote payload.")

        # Finnhub documents unknown symbols as an all-zero quote (c=0, t=0, ...).
        current = payload.get("c")
        timestamp = payload.get("t")
        if current in (None, 0, 0.0, "0") and timestamp in (None, 0, 0.0, "0"):
            return None

        try:
            price = Decimal(str(current))
        except (InvalidOperation, TypeError) as exc:
            raise ProviderUnavailable("Finnhub returned an unreadable price.") from exc

        if price <= 0:
            return None

        try:
            as_of = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        except (TypeError, ValueError, OSError) as exc:
            raise ProviderUnavailable(
                "Finnhub returned an unreadable quote timestamp."
            ) from exc

        return QuoteResult(price=price, as_of=as_of, source="finnhub")

    def _request(self, symbol: str) -> httpx.Response:
        headers = {"X-Finnhub-Token": self._api_key}
        params = {"symbol": symbol}
        try:
            response = self._client.get(_QUOTE_URL, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("Finnhub request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("Finnhub network error.") from exc

        if response.status_code == 429:
            time.sleep(_RETRY_WAIT_SECONDS)
            try:
                response = self._client.get(_QUOTE_URL, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise ProviderUnavailable("Finnhub request timed out.") from exc
            except httpx.HTTPError as exc:
                raise ProviderUnavailable("Finnhub network error.") from exc
            if response.status_code == 429:
                raise ProviderUnavailable("Finnhub rate limit exceeded.")

        if response.status_code >= 500:
            raise ProviderUnavailable(
                f"Finnhub returned HTTP {response.status_code}."
            )
        if response.status_code >= 400:
            logger.warning(
                "Finnhub quote request failed with HTTP %s for symbol %s",
                response.status_code,
                symbol,
            )
            raise ProviderUnavailable(
                f"Finnhub returned HTTP {response.status_code}."
            )
        return response
