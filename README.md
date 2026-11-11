# portfolio-agent

Portfolio tracker with an analysis agent and MCP access. FastAPI, Postgres (Neon), WorkOS AuthKit (GitHub or Google), Claude.

## Local setup

Requires Python 3.12. Use the project virtualenv at `.venv` (not a base Anaconda env).

```bash
cd portfolio-agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-dev.txt
cp .env.example .env
# Fill in every value in .env (see below)
alembic upgrade head
uvicorn app.main:app --host localhost --port 8000
```

Run tests (calculation tests always; isolation tests need `TEST_DATABASE_URL`):

```bash
pytest
```

On startup the process prints:

- `WorkOS redirect URI` — register this under WorkOS → Redirects
- `MCP resource URL` — register this under WorkOS Connect → Resource Indicators (and set as default)

Open `http://localhost:8000`.

## Environment variables

| Name | Purpose |
|---|---|
| `BASE_URL` | Public origin, no trailing slash. Local: `http://localhost:8000` |
| `ALLOWED_ORIGINS` | Comma-separated browser origins allowed to call `/mcp` |
| `DATABASE_URL` | Neon **pooled** Postgres URL (`sslmode=require`) |
| `DATABASE_URL_DIRECT` | Neon **direct** URL for Alembic (`sslmode=require`) |
| `WORKOS_API_KEY` | WorkOS API key |
| `WORKOS_CLIENT_ID` | WorkOS client id |
| `WORKOS_COOKIE_PASSWORD` | Fernet key, min 32 chars: `python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `AUTHKIT_DOMAIN` | e.g. `https://your-project.authkit.app` |
| `FINNHUB_API_KEY` | Finnhub API key (free plan; sent as `X-Finnhub-Token`) |

## Market data

Provider: [Finnhub](https://finnhub.io/) `/quote` for US equities.

**Verified against Finnhub docs on 2026-11-11** ([Quote API](https://www.finnhub.io/docs/api/quote), rate limit notes in the Finnhub docs and free-plan reports):

- `/quote` returns `c` (current price), `d` / `dp` (change), `h` / `l` / `o` / `pc` (session stats), and `t` (UNIX timestamp of the quote).
- An unknown symbol returns an all-zero payload (including `c=0` and `t=0`). This app treats that as not found, never as a price of zero.
- Free plan: 60 API calls per minute. Over the limit returns HTTP 429.
- `/stock/candle` is not available on the free plan (returns access denied). Price history is built from our own daily snapshots instead.

**Caching and status**

- Successful fetches are stored in `quotes`. If a ticker was fetched in the last 5 minutes, the dashboard reuses that row and does not call Finnhub.
- Status labels (America/New_York times):
  - **Live:** market open and the quote `as_of` is within the last 20 minutes.
  - **Market closed, as of …:** market closed; showing the last trade or close time.
  - **Delayed: showing last saved price from …:** provider failed or the quote is older than 20 minutes while the market is open.
  - **Price unavailable:** no provider price and nothing stored.
- US market hours are weekdays 9:30 to 16:00 ET. **Holidays are not modeled.**

**Daily snapshot job**

- Render cron `portfolio-price-snapshot` runs `python -m app.jobs.snapshot_prices` on weekdays at `30 22 * * 1-5` UTC (after the US close).
- One row per ticker per New York trading day (`snapshot_date`), for distinct tickers from lots and favorites. Re-runs the same day do not create duplicates.
- The job loads `JobSettings` (`DATABASE_URL` + `FINNHUB_API_KEY` only). It does not need WorkOS variables.

## WorkOS checklist (short)

1. Enable AuthKit; enable both GitHub and Google as sign-in methods.
2. Redirect URI = printed `WorkOS redirect URI` (`/callback`).
3. Sign-out URI = `BASE_URL` (or `/`).
4. Initiate login URI = `BASE_URL/login`.
5. Connect → enable CIMD and DCR; add MCP resource URL; set as default.

## Render

Live URL: https://portfolio-agent-nt7v.onrender.com

See `render.yaml`. Start command runs migrations then Uvicorn on `$PORT`. Set the same env vars in the Render dashboard; `BASE_URL` must be the public HTTPS URL. Render assigned a suffixed hostname; `BASE_URL` and `ALLOWED_ORIGINS` must match it exactly.

## Health

`GET /healthz` — plain liveness (not the MCP endpoint).

## MCP

Streamable HTTP at `/mcp`, protected by WorkOS AuthKit (`AuthKitProvider`). Tool available today: `whoami`.
