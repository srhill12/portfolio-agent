# AI Workflow Log

## 2026-10-17: MCP authorization research spike

**Tool:** Cursor agent, research-only prompt (no code), asked to verify against current documentation rather than memory.

**Prompt intent:** Compare three ways to add OAuth to the MCP endpoint with GitHub as identity provider: FastMCP built-in GitHub auth, official MCP SDK with a hosted authorization server, and personal access tokens as fallback.

**Output accepted:** Recommendation of WorkOS AuthKit as authorization server with GitHub as the login method, giving one user identity across web, API, agent, and MCP.

**Output corrected:** The report stated GitHub OAuth Apps allow only one callback URL and counted that against Option 1. GitHub's registration form currently allows up to 10 redirect URIs. The recommendation still holds on other grounds (single identity layer, alignment with current MCP authorization model, free tier), but the reasoning was corrected.

**Verified independently:** [fill in after checking WorkOS pricing and the FastMCP AuthKit docs]

## 2026-10-17: Day 1 build corrections

- **Migration bug:** Generated migration created Postgres enum types twice (explicitly and again via create_table), failing on a fresh database. Diagnosed from the traceback, directed the fix (create_type=False on columns, single explicit creation), and verified reversibility with upgrade, downgrade to base, and upgrade.
- **Rejected cleanup step:** Agent suggested dropping possibly orphaned enum types with psql. Rejected: Postgres DDL is transactional, so the failed migration had already rolled back, and the command referenced an environment variable that only existed in .env, not the shell.
- **Rejected setup step:** Agent's run instructions included `cp .env.example .env`, which would have overwritten the configured secrets file. Skipped and added the new variables manually.
- **Corrected key generation:** Agent suggested `openssl rand -base64 32` for the session cookie key, which requires a URL-safe base64 Fernet key. Standard base64 can include characters Fernet rejects. Generated the key with Python's urlsafe_b64encode instead.