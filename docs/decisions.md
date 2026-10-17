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