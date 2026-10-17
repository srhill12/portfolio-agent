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