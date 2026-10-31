# Database Sidekick

A separate rebuild of `Database-Copilot-Backboard` for Hacktoberfest Raleigh. The original folder is unchanged. Keeps Supabase login, PostgreSQL/MySQL/SQLite connections, schema inspection, natural-language SQL, multi-step tool execution, result tables, and human approval of INSERT/UPDATE and new table creation.

Gemma 4 replaces Groq/Llama entirely. The default uses Google's official `google-genai` client and your Gemini API key to call hosted `gemma-4-26b-a4b-it`. No Ollama installation, model download, or local GPU is needed. Availability and quota depend on your Google API project.

## Run locally (PowerShell)

Create a Supabase project and run `backend/supabase.sql` in its SQL editor. Copy `backend/.env.example` to `backend/.env`, and `frontend/.env.example` to `frontend/.env.local`. Fill in your own Supabase values and set `GEMINI_API_KEY` in `backend/.env`. Reuse your original Supabase project if desired; no need to recreate its existing table. Set `LLM_PROVIDER=gemini` and `GEMMA_MODEL=gemma-4-26b-a4b-it` if you previously copied the Ollama configuration. The service-role key belongs only in the backend.

Backend, in one terminal:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

Frontend, in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000, sign up, and connect a database. Optional: run `python seed_demo.py` in backend to create a fictional customer/orders database and print its connection URL. The sample-data generator never overwrites an existing database.

For Linux/macOS, use `.venv/bin/python` in place of `.venv\Scripts\python`.

## Model configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| LLM_PROVIDER | gemini | `gemini`, `ollama`, or `openai-compatible` |
| GEMMA_MODEL | gemma-4-26b-a4b-it | Hosted Gemma 4; `gemma-4-31b-it` is also supported by Google |
| GEMINI_API_KEY | required for gemini | Your Google AI Studio API key; backend only |
| LLM_BASE_URL | http://localhost:11434 | Ollama origin; compatible servers need their `/v1` base URL |
| LLM_API_KEY | empty | Optional hosted-model bearer token |

The Gemini provider uses native function calls and returns SQL execution to the existing approval loop; the SDK never executes SQL automatically. Opaque function-call signatures are retained across turns. Optional OpenAI-compatible servers must provide native tool calling for the selected Gemma model. There is no silent fallback to another model. The UI shows the configured runtime; this badge reports configuration, not a live inference readiness test. A live model still needs to be installed/reachable. The adapters cap generated tokens. Optional Ollama mode keeps the model warm between requests. SQL results shown to the model are limited to 50 rows, and the loop has query, result-cell, and time budgets.

## Safety and behavior

Reads execute automatically. INSERT/UPDATE/CREATE TABLE pause for approval and execute only the SQL saved server-side. Direct `/query/run` is read-only. A shared parser rejects multiple statements, nested writes in reads, SELECT INTO, and destructive/administrative statements. Multiple tool calls from a model are rejected with matching tool results, so the next model turn has a valid conversation. Forced summaries disable tools.

Use minimally privileged database credentials and read-only roles for read-only connections. A SQL statement classifier is not a database sandbox: functions, triggers, dialect-specific behavior, and heavy queries still require database-level permissions and timeouts. Query execution currently fetches all rows before the agent cell budget is checked. Chat history is in memory; restarting the backend clears it and pending approvals. Run one worker. Supabase connection strings are stored as in the original app; protect the project and its service key.

## Verify

```powershell
cd backend
.venv\Scripts\python -m unittest discover -s tests -v
cd ../frontend
npm run build
```

Tests use fictional SQLite data and mocked model responses; they do not prove live Gemma quality. Actual Supabase and Gemma integration requires your configuration. No credentials are copied from the original folder.

See [HACKATHON.md](HACKATHON.md) for prize alignment, a demo script, and Maritime packaging. This rebuild is derived from the existing app: disclose the starting point and check organizer rules before claiming a new or open-source submission. No license has been invented for the original source.

## Optional offline Ollama mode

Only if you want local inference, install Ollama, run `ollama pull gemma4:e4b`, and set `LLM_PROVIDER=ollama`, `GEMMA_MODEL=gemma4:e4b`, and `LLM_BASE_URL=http://localhost:11434`. Your Gemini key is not used by this mode.

Google reference: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api

## Images and ER diagrams

Click **+ Image** in chat to attach up to three PNG/JPEG/WebP files (4 MB each). Thumbnails can be removed before sending. Images are sent inline to Google's Gemini API alongside your message, and are retained only in the app's in-memory conversation and browser state, not uploaded to Supabase Storage. They are resubmitted with conversation context until that round ages out of history. Google processing/retention follows your API project terms. PDFs, SVGs, and HEIC are not supported; export diagrams as PNG.

Try: "Implement this ER diagram. Inspect my schema, explain unclear details, and propose the missing tables with their keys and relationships."

Gemma can create new tables in the default/public schema, one approved statement at a time. The schema cache refreshes after approved table creation. Existing table modifications (ALTER), DROP/DELETE, views/functions/triggers, CREATE OR REPLACE, and CREATE TABLE AS SELECT remain blocked. These approvals are independent commits, not one atomic migration; if a later table fails, earlier approved tables remain. Database credentials must have CREATE privilege for table creation to succeed. New Supabase tables do not get automatic application-specific RLS policies from this feature; review access policies before using them with the Data API.

Image-only messages default to analysis and suggestions; include an explicit implementation request to propose changes. Unclear diagrams should lead to clarification, not invented columns. Model interpretation must still be reviewed. Current automated tests cover image formatting/validation and approved DDL with mocked responses, not live visual recognition quality.
