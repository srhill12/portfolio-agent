# AI Workflow Log

## How I work

Cursor (agent mode) writes code from scoped prompts; a separate Claude chat reviews each gate against the assessment brief and the actual source before I merge; I decide, run the verification steps myself, and commit from the terminal. Feature work goes on a branch and is reviewed before merging to main.

## 2026-10-17: MCP authorization research spike

**Tool:** Cursor agent, research-only prompt (no code), asked to verify against current documentation rather than memory.

**Prompt intent:** Compare three ways to add OAuth to the MCP endpoint with GitHub as identity provider: FastMCP built-in GitHub auth, official MCP SDK with a hosted authorization server, and personal access tokens as fallback.

**Output accepted:** Recommendation of WorkOS AuthKit as authorization server with GitHub as the login method, giving one user identity across web, API, agent, and MCP.

**Output corrected:** The report stated GitHub OAuth Apps allow only one callback URL and counted that against Option 1. GitHub's registration form currently allows up to 10 redirect URIs. The recommendation still holds on other grounds (single identity layer, alignment with current MCP authorization model, free tier), but the reasoning was corrected.

**Verified independently:** The AuthKit design worked end to end: web sign-in and Claude Code MCP OAuth locally on 2026-10-18, and on the production Render URL on 2026-11-10.

## 2026-10-17: Day 1 build corrections

- **Migration bug:** Generated migration created Postgres enum types twice (explicitly and again via create_table), failing on a fresh database. Diagnosed from the traceback, directed the fix (create_type=False on columns, single explicit creation), and verified reversibility with upgrade, downgrade to base, and upgrade.
- **Rejected cleanup step:** Agent suggested dropping possibly orphaned enum types with psql. Rejected: Postgres DDL is transactional, so the failed migration had already rolled back, and the command referenced an environment variable that only existed in .env, not the shell.
- **Rejected setup step:** Agent's run instructions included `cp .env.example .env`, which would have overwritten the configured secrets file. Skipped and added the new variables manually.
- **Corrected key generation:** Agent suggested `openssl rand -base64 32` for the session cookie key, which requires a URL-safe base64 Fernet key. Standard base64 can include characters Fernet rejects. Generated the key with Python's urlsafe_b64encode instead.

## 2026-10-18: Rubric cross-check of my traceability matrix
- Compared my requirements matrix line by line against the assessment brief. Found four gaps: no row for stack justification, no row for client-brief assumptions, "no generic purple gradients" missing from the copy review, and the video tracked as one row instead of each required topic. Added K1, K2, and V1 to V9, and marked self-imposed extras (E3, U3, P4, G8) as beyond rubric so they are the first things cut if time runs short.
- Decided to add Google as a second sign-in method after noting that a reviewer without a GitHub account would make the deliverable inaccessible, which the brief treats as a failed submission.

## 2026-11-10: Production deployment findings
- Render assigned a suffixed hostname, so the URL I configured did not match. Updated BASE_URL and ALLOWED_ORIGINS and confirmed the printed callback and MCP URLs in the deploy log.
- Sign-in failed with "Invalid client ID." I traced it by inspecting the /login redirect with curl: the client_id ended in "+", a URL-encoded trailing space pasted into the Render environment variable. Fixed the value, then had the agent make Settings strip whitespace from every environment variable, with a test, so the same operator mistake cannot break sign-in again.
- The AuthKit sign-in page showed an email field and "Continue with SSO" from enterprise SSO. Disabled SSO, password, and Magic Auth so the page offers only the two OAuth buttons, matching the requirement for OAuth-based sign-in.
- Claude Code's MCP consent screen warns about a localhost redirect. Confirmed this is expected for CLI clients (Claude Code receives the token on a temporary local port) and noted it for the README connection instructions.

## 2026-11-11: Gate 2 session 1 review (accounts, holdings, calculations)
- Before building, review of the existing schema found the lot idempotency key was unique across all users rather than per user. Changed it to unique per (user_id, idempotency_key) with a reversible migration, verified on a separate Neon test branch.
- Review of the agent's code before merging found and I directed fixes for:
  - Test setup that loaded my .env, leaving the production DATABASE_URL in place. Added a guard that refuses to run if the test database host matches production.
  - Dashboard showing raw database decimals (10.00000000, and an average cost with 25 decimal places). Added money, quantity, and percent formatting.
  - Percent rounding that turned 14.19% into 14%.
  - Portfolio total cost silently excluding holdings with no price, which would understate what the client invested. Split into total cost and priced cost.
  - An update path that could leave a holding half modified when validation failed.
  - Very large quantities causing a server error instead of a clear message.
- Agent reported tests passing, but plain `pytest` failed on a clean shell because the project root was not on the import path. Added pytest.ini so the README instructions work for someone taking over the project.
- Found during production testing: after about five minutes on the page, Sign out did not end the WorkOS session, so the next sign-in skipped the provider choice. Read the WorkOS SDK source and found the logout URL call first validates the short-lived access token and raises when it has expired, which our code swallowed silently. Fixed it to refresh the session first, log a warning instead of failing silently, and added tests. Confirmed on production by waiting more than six minutes before signing out.

## 2026-11-11: Gate 2 session 2 review (market data)
- The agent verified Finnhub's free-plan endpoints and limits from the documentation before coding, as instructed. Price history is built from our own daily snapshots because historical candles are not part of the free plan.
- Review before merging found three issues the passing test suite did not cover: deleting an account with holdings would fail because the ORM tried to null the lots' account_id instead of relying on the database cascade; the once-per-minute price refresh limit lived in a browser cookie, so it could be bypassed and burn the shared API quota; and a provider outage after market hours was labeled "Market closed", hiding that the price was old. Fixed all three and added tests for each, including the missing happy-path test for account deletion.
