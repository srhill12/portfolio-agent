# Decision Log

## 2026-10-17: Stack and delivery approach

**Decision:** Single FastAPI service with server-rendered pages (Jinja and HTMX), Postgres on Neon, hosted on Render, GitHub OAuth, Claude for analysis, MCP mounted in the same service.

**Alternatives considered:** Next.js frontend with a separate API (two deployments, more surface area); Supabase (free projects pause after inactivity); yfinance for market data (unofficial scraper, hard to defend to a client).

**Why:** One deployment and one authorization layer means the web app, agent, and MCP tools all call the same service functions, so access rules cannot drift between them. Python throughout keeps the codebase in one language for whoever takes it over.

## 2026-10-17: Adjustments after checking the plan against requirements

- **Scheduler:** Render cron job instead of GitHub Actions. GitHub disables scheduled workflows in public repositories after 60 days without commits, which would silently stop the monthly analysis after delivery.
- **Price history:** daily closing-price snapshot for held and favorited tickers, so history exists even when no one opens the app.
- **Concurrent runs:** a run already in progress blocks a second manual run, in addition to the database rule allowing one scheduled run per month.
- **Weekend data:** staleness is market-aware. Friday's close shown on Sunday is labeled as the last close, not as stale.
- **Account types:** named "investment" and "retirement" to match the client's own words.
- **MCP authorization:** attempt OAuth first, time-boxed. Fall back to scoped, revocable personal access tokens issued only after OAuth sign-in, and document why.

## 2026-10-17: Authorization architecture

**Decision:** WorkOS AuthKit as the authorization server, with GitHub as the sign-in method, for both the web app and the MCP endpoint. The app acts as the resource server and validates tokens on every request.

**Alternatives considered:** FastMCP's built-in GitHub OAuth proxy (no added vendor, but two separate login paths for web and MCP); personal access tokens (simplest, but not OAuth and poorly supported by browser-based MCP clients).

**Why:** One identity for every way a user reaches their portfolio, so a single authorization rule applies everywhere. Matches the current MCP authorization model, where the app is the resource server and a dedicated authorization server handles sign-in. No cost at this scale.

**Fallback plan:** If the spike fails, FastMCP's GitHub provider; if that fails, scoped and revocable personal access tokens issued after sign-in, with the tradeoff documented.

**Amendment (2026-10-18):** Added Google as a second sign-in method. The assessment fails any deliverable a reviewer cannot access, and a GitHub-only sign-in assumed every reviewer has a GitHub account. AuthKit's hosted page serves both web and MCP sign-in, so this required configuration only, no code changes. Staging uses WorkOS demo OAuth credentials for both GitHub and Google, so provider consent screens show WorkOS rather than the app name; a production handoff would register the client's own GitHub and Google OAuth apps.

- AuthKit sign-in methods are limited to GitHub and Google. Email and password, Magic Auth, and enterprise SSO are disabled, so the hosted sign-in page shows only the two OAuth buttons.
- Staging constraint: WorkOS issues MCP tokens for the default resource indicator. The production /mcp URL is the default; local MCP testing requires temporarily switching the default to http://localhost:8000/mcp.

## 2026-10-18: Render Starter plan in Ohio region

**Decision:** Render Starter plan in Ohio region. Free tier sleeps after 15 minutes idle, which adds cold-start delays that can break OAuth sign-in and MCP connections for a reviewer. Ohio co-locates the app with the Neon database. Scheduled jobs will run as a separate Render cron service.

## 2026-11-11: Separate test database branch
**Decision:** Isolation and database tests run against a dedicated Neon branch named test, set in TEST_DATABASE_URL. Each test runs inside a transaction that is rolled back.
**Why:** The schema uses Postgres-only features (partial unique indexes, enums, JSONB), so an in-memory SQLite substitute would not test the real constraints. A guard refuses to run if the test host matches production.

## 2026-11-11: Money and rounding
**Decision:** All money and quantity math uses Decimal at full precision. Rounding happens only for display: currency to cents with round-half-up, percentages to two places.
**Why:** Rounding intermediate values causes totals that do not add up. Keeping display rounding separate means calculations can be checked exactly against a hand calculation.

## 2026-11-11: Finnhub for live quotes
**Decision:** Use Finnhub's free-plan `/quote` endpoint for US equity prices, with the API key sent only in the `X-Finnhub-Token` header.
**Alternatives considered:** yfinance (unofficial scraper, brittle for a client handoff); paid Finnhub historical candle endpoints (not on the free plan).
**Why:** Documented HTTP API, free tier at 60 calls per minute, and a clear all-zero response for unknown symbols so the app can show "unavailable" instead of a fake zero.

## 2026-11-11: Price history from daily snapshots
**Decision:** Build price history by storing one quote row per ticker per New York trading day (`snapshot_date`), filled by a weekday Render cron after the US close. Live dashboard fetches write separate cache rows with `snapshot_date` null.
**Alternatives considered:** Finnhub `/stock/candle` (paid on current free plans); pulling history only when a user opens the research page (would leave gaps on days nobody visits).
**Why:** The free plan does not include candles, and a scheduled snapshot keeps history for held and favorited tickers even when no one opens the app.

