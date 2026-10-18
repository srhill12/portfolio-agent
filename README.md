# portfolio-agent

Portfolio tracker with an analysis agent and MCP access. FastAPI, Postgres (Neon), WorkOS AuthKit (GitHub or Google), Claude.

## Local setup

Requires Python 3.12. Use the project virtualenv at `.venv` (not a base Anaconda env).

```bash
cd portfolio-agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
# Fill in every value in .env (see below)
alembic upgrade head
uvicorn app.main:app --host localhost --port 8000
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
| `WORKOS_COOKIE_PASSWORD` | Fernet key, min 32 chars: `openssl rand -base64 32` |
| `AUTHKIT_DOMAIN` | e.g. `https://your-project.authkit.app` |

## WorkOS checklist (short)

1. Enable AuthKit; enable both GitHub and Google as sign-in methods.
2. Redirect URI = printed `WorkOS redirect URI` (`/callback`).
3. Sign-out URI = `BASE_URL` (or `/`).
4. Initiate login URI = `BASE_URL/login`.
5. Connect → enable CIMD and DCR; add MCP resource URL; set as default.

## Render

See `render.yaml`. Start command runs migrations then Uvicorn on `$PORT`. Set the same env vars in the Render dashboard; `BASE_URL` must be the public HTTPS URL.

## Health

`GET /healthz` — plain liveness (not the MCP endpoint).

## MCP

Streamable HTTP at `/mcp`, protected by WorkOS AuthKit (`AuthKitProvider`). Tool available today: `whoami`.
