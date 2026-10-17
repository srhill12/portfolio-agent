# AI Workflow Log

## 2026-10-17: MCP authorization research spike

**Tool:** Cursor agent, research-only prompt (no code), asked to verify against current documentation rather than memory.

**Prompt intent:** Compare three ways to add OAuth to the MCP endpoint with GitHub as identity provider: FastMCP built-in GitHub auth, official MCP SDK with a hosted authorization server, and personal access tokens as fallback.

**Output accepted:** Recommendation of WorkOS AuthKit as authorization server with GitHub as the login method, giving one user identity across web, API, agent, and MCP.

**Output corrected:** The report stated GitHub OAuth Apps allow only one callback URL and counted that against Option 1. GitHub's registration form currently allows up to 10 redirect URIs. The recommendation still holds on other grounds (single identity layer, alignment with current MCP authorization model, free tier), but the reasoning was corrected.

**Verified independently:** [fill in after checking WorkOS pricing and the FastMCP AuthKit docs]