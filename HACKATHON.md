# Hacktoberfest Raleigh demo

Verified from the event page on October 31, 2026:
https://www.mlh.com/events/hacktoberfest-hack-day-raleigh-x-hack_ncstate-applied-ai-club-at-nc-state

| Category | What this rebuild contributes | Still needed for submission |
| --- | --- | --- |
| Best Use of Gemma 4 | Gemma 4 drives the actual query/tool/result loop, including recovery from SQL errors and write approval. Local inference is available through Ollama. | Run a real Gemma demo and capture it. |
| Best Open-Source AI Project | Open-weight model, inspectable tool harness, SQL policy tests, repeatable fictional dataset. | Publish the source with an appropriate license after confirming rights to the original code; disclose the existing app and identify hack-day changes. Confirm eligibility with organizers. |
| Best Use of Maritime | Root Dockerfile, one-port web UI/API reverse proxy, health endpoint, runtime-selected model server. | Actually deploy on Maritime, show sleep/wake and hosting behavior, and demonstrate meaningful platform use. Packaging alone is not a completed integration or eligibility guarantee. |

## Two-minute demo

1. Run `python seed_demo.py` in backend and connect the printed SQLite URL through onboarding.
2. Ask: "Describe the tables and their relationships."
3. Ask: "Which customers have the highest paid order totals? Show names and totals."
   Expected data: Avery 200, Sam 30. Gemma must join and aggregate the real tables.
4. Ask: "Check customers for missing city values." Expected: Sam.
5. Ask: "Set Sam's city to Raleigh." Show the SQL approval card; reject it first.
6. Ask the same request, approve it, then ask Gemma to verify the stored city.
7. Ask to drop the orders table. The server blocks destructive statements even if the model requests one.

Pitch: "A small open-weight model turns questions into auditable database actions. Read queries run autonomously; every write remains reviewable. Developers get the original SQL, real results, and a grounded explanation."

## Deployment on Maritime

The Dockerfile runs the UI and authenticated API as a web agent behind a single `$PORT`. It follows the public-web-app contract, not Maritime's unauthenticated chat-channel contract. Supabase login remains required for database access.

Build an image with the public frontend Supabase values:

```sh
docker build --build-arg NEXT_PUBLIC_SUPABASE_URL=https://YOUR.supabase.co --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY -t YOUR_REGISTRY/database-copilot-gemma4:latest .
```

Push to your registry, then select that image in Maritime's new-agent UI. Set backend secrets through Maritime's Env UI: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `LLM_PROVIDER`, `GEMMA_MODEL`, `GEMINI_API_KEY` (native Gemini mode), or `LLM_BASE_URL` and optionally `LLM_API_KEY` for other providers. Set `ALLOWED_ORIGINS` to the resulting app URL. The frontend talks to `/api/backend` on its own origin. `/health` is proxied to the API. Never provide the service role key as a Docker build argument.

For cloud deployment the default is `LLM_PROVIDER=gemini`, `GEMMA_MODEL=gemma-4-26b-a4b-it`, and your backend-only `GEMINI_API_KEY`. No separate model server is needed. Alternatively use a reachable hosted Gemma 4 server (for example your own vLLM server configured for native Gemma tool calling) with `LLM_PROVIDER=openai-compatible` and its `/v1` URL. The default localhost Ollama endpoint requires Ollama on the same host; it will not reach your laptop from a cloud container. Do not assume Maritime's model proxy offers Gemma 4 without checking its current catalog.

The Docker image has not been deployed or container-tested in this workspace. Supabase stores connections; chat history and pending approvals remain in process memory and reset on process restart. Use one API worker. Review behavior across an actual Maritime sleep/wake before demonstrating it.

References: [Maritime public web agents](https://maritime.sh/docs/web-apps), [container contract](https://maritime.sh/docs/frameworks/custom), [Ollama Gemma 4](https://ollama.com/library/gemma4).
