# Requirements Traceability

Maps each client and assessment requirement to where it is implemented and how it was verified. Updated at each delivery checkpoint.

**Status values:** Not started · In progress · Verified

Rows marked (beyond rubric) are self-imposed quality bars, not assessment requirements.

**Checkpoints:** 0 Setup · 1 Deployed skeleton · 2 Holdings, market data, calculations · 3 Agent and MCP · 4 Full walkthrough · 5 Submission

| ID | Requirement | Implementation | Verification | Checkpoint | Status |
|---|---|---|---|---|---|
| D1 | Live site; reviewer can sign in and use required functionality | Render web service | Second account signs in from a private window, once with GitHub and once with Google | 1, 4 | Not started |
| K1 | Stack fit, alternatives considered, and operational tradeoffs explained | docs/decisions.md and video topic 2 | Document review | 0, 5 | In progress |
| K2 | Client-brief assumptions documented; consequential ones explained in video | docs/assumptions.md and video topic 1 | Document review | 0, 5 | In progress |
| A1 | OAuth sign-in, no local passwords | WorkOS AuthKit (GitHub or Google) | No password fields or tables exist | 1 | Not started |
| A2 | Users access and change only their own portfolio: web app | Session-derived user ID; all queries filter by user | Cross-user test: second user gets 404 on first user's holding | 2 | Not started |
| A3 | Same isolation: backend API | Shared service layer | Cross-user test via API | 2 | Not started |
| A4 | Same isolation: agent | User ID injected server-side into agent tools | Code review and test that tools ignore model-supplied IDs | 3 | Not started |
| A5 | Same isolation: MCP | Token resolves to user ID; shared service layer | MCP session as second user cannot read or edit first user's data | 3 | Not started |
| A6 | MCP authorization via OAuth; fallback documented if not feasible | Authorization layer | MCP client connects through OAuth flow | 1, 3 | Not started |
| H1 | Persist investment and retirement accounts, tickers, quantities, purchase prices | Accounts and lots tables (Postgres) | Data survives redeploy | 1, 2 | Not started |
| H2 | Add and update holdings | Holdings forms and API | Manual walkthrough | 2 | Not started |
| M1 | Quotes from an external market-data API | Quote service | Live quote displayed with source | 2 | Not started |
| M2 | Store price history | Quotes table with daily snapshot job | Rows accumulate daily; chart on research page | 2 | Not started |
| M3 | Timestamps, stale data, and unavailable data are understandable | Market-aware status labels | Screenshot of each state | 2 | Not started |
| M4 | Provider refresh limits explained | README and in-app note | Document review | 2 | Not started |
| C1 | Holding and portfolio value, unrealized gain/loss | Calculations module using exact decimal math | Matches hand-computed spreadsheet | 2 | Not started |
| C2 | Combined positions across accounts | Weighted-average cost rollup | Same ticker in two accounts matches spreadsheet | 2 | Not started |
| C3 | Currency, fees, dividends, and cost basis assumptions documented | docs/assumptions.md and README | Document review | 2 | Not started |
| F1 | Maintain favorite tickers | Favorites table and UI | Walkthrough | 2 | Not started |
| F2 | Inspect stock information for basic research | Research page: quote, profile, news, history | Walkthrough | 2 | Not started |
| G1 | Monthly analysis | Scheduled job | Manually fired job produces a scheduled run | 3 | Not started |
| G2 | On-demand analysis trigger | Run-analysis button | Walkthrough | 3 | Not started |
| G3 | Analysis and reasoned recommendations saved | Analysis runs table with input snapshot, tool calls, output, model, prompt version | Run history page | 3 | Not started |
| G4 | Performance and concentration explained | Structured output fields | Evaluation cases | 3, 4 | Not started |
| G5 | Missing and stale inputs identified | Data-gaps output field | Stale and missing-data evaluation cases | 3, 4 | Not started |
| G6 | Verified calculations and authorized tools only | Tools call the calculations module; output numbers verified against computed values | Deliberately wrong number is caught | 3 | Not started |
| G7 | Basis and limitations explained; no trade execution | Output fields and disclaimer; agent has read-only tools | Code and UI review | 3 | Not started |
| G8 | Bounded, auditable agent runs (beyond rubric) | Application-enforced turn limit; same checks for scheduled and manual runs | Code review; inspect a saved run | 3 | Not started |
| P1 | MCP: retrieve holdings, metrics, latest analysis | MCP tools with output schemas | MCP client session | 3 | Not started |
| P2 | MCP: add and update holdings | MCP tools with idempotency keys | MCP client session; retry creates no duplicate | 3 | Not started |
| P3 | MCP: input validation and recoverable errors | Schema validation; actionable error messages | Invalid input rejected with a clear message | 3 | Not started |
| P4 | MCP transport security (beyond rubric) | Origin validation, bearer tokens in headers only, token audience checked | Request with disallowed origin rejected | 3 | Not started |
| P5 | MCP connection instructions | README section; SDK and protocol versions pinned | Followed from scratch on a clean setup | 3, 5 | Not started |
| R1 | Invalid input handling | Validation on client and server | Document and walkthrough review | 4 | Not started |
| R2 | External-service failure handling | Fallbacks; failures never shown as empty data | Simulated provider and model failures | 3, 4 | Not started |
| R3 | Retries do not duplicate holdings | Idempotency key with unique constraint | Test | 2 | Not started |
| R4 | Repeated agent runs do not mislead history | One scheduled run per month enforced by database; manual runs labeled; in-progress lock | Double-click and double-trigger tests | 3 | Not started |
| U1 | Coherent navigation and readable layouts | Design pass | Walkthrough including phone width | 4 | Not started |
| U2 | Loading, empty, and error states | All pages | Per-page checklist | 4 | Not started |
| U3 | Accessible controls (beyond rubric) | Native buttons, visible focus, status announcements | Keyboard-only walkthrough | 4 | Not started |
| U4 | Reviewed design and copy | Copy pass | Codebase scan of README, docs, and templates for em dashes, stock phrasing, and no generic purple gradients | 4 | Not started |
| U5 | Design references and iterations documented | docs/design/ | Screenshots present | 0, 4 | Not started |
| S1 | Fictional data only; no credentials in code or recording | Sample portfolio; environment variables | Secret scan of full git history | 1, 5 | Not started |
| E1 | Evaluation cases: inputs, expected behavior, actual results, assessment | evals/ | Document review | 3, 4 | Not started |
| E2 | Model and configuration identified | Recorded per run with prompt and case-set versions | Document review | 3 | Not started |
| E3 | Development and held-out cases separated; pass rules written before runs (beyond rubric) | evals/ | Document review | 3, 4 | Not started |
| E4 | Observed problems and changes recorded | evals/ findings section | Document review | 4 | Not started |
| E5 | Grounding, stale and missing data, unsupported conclusions addressed | Evaluation interpretation | Document review | 4 | Not started |
| E6 | Numerical correctness separated from recommendation quality | Separate result columns | Document review | 4 | Not started |
| RP1 | README: setup, configuration, data model, architecture, deployment, limitations | README | Checklist | 5 | Not started |
| RP2 | Instructions: sign-in, MCP connection, on-demand agent trigger | README | Followed from scratch | 5 | Not started |
| RP3 | Operating costs, provider limits, failure handling, takeover information | docs/handoff.md | Document review | 5 | Not started |
| V1 | Presentation video: on camera, non-technical audience, 6 to 8 minutes, 10 minutes max | Recording | Topic checklist with timestamps | 5 | Not started |
| V2 | Client outcome and assumptions | Recording | Topic checklist with timestamps | 5 | Not started |
| V3 | Architecture, stack, and deployment tradeoffs | Recording | Topic checklist with timestamps | 5 | Not started |
| V4 | Agent and MCP capabilities and access control | Recording | Topic checklist with timestamps | 5 | Not started |
| V5 | Agentic coding workflow with concrete verified, corrected, or rejected examples | Recording | Topic checklist with timestamps | 5 | Not started |
| V6 | Evaluation evidence and grounding | Recording | Topic checklist with timestamps | 5 | Not started |
| V7 | Direct answer to "if you changed models tomorrow, how would you know the agent still works" | Recording | Topic checklist with timestamps | 5 | Not started |
| V8 | Design and copy direction with references | Recording | Topic checklist with timestamps | 5 | Not started |
| V9 | Client handoff: limitations, costs, risks, next steps | Recording | Topic checklist with timestamps | 5 | Not started |
| X1 | All deliverables accessible to someone outside the developer's accounts | Submission links | Logged-out check | 5 | Not started |
