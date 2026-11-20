# NBA Fantasy Chatbot Security Tests

CMPE 411 project on prompt injection and jailbreak testing for an H2H 9-cat NBA Fantasy chatbot. The local demo reads a fixed player snapshot from `data/players.json` and compares two selected players by points (PTS), rebounds (REB), and turnovers (TO).

## Set up on Windows

Use Python 3.13, the version used to verify the project. Run these commands in PowerShell.

```powershell
git clone https://github.com/yagizceyhan/Fantasy_LLM_chatbot_prompt_injection.git
Set-Location .\Fantasy_LLM_chatbot_prompt_injection
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

The suite defines **44 test cases: 33 unit and 11 API integration cases**. Provider tests use `httpx.MockTransport` or controlled stubs, so `pytest` does not make external model requests or consume API quota. Cases and remaining gaps are mapped in [the test design](testdesign.md#6-local-test-inventory-and-implementation-status).

The screenshot supplied on 20 November 2026 verifies the earlier 23-case baseline. The mode and Gemini changes require a fresh run before recording a new pass count. Adapter tests establish local request/response handling, not resistance of a real model to prompt injection.

## Working modes

`CHAT_MODE` selects the mode when Uvicorn imports `app.main:app`. The default is `demo`. An unknown mode fails at application creation.

| Mode | Provider | Behavior for a valid comparison |
| --- | --- | --- |
| `demo` | None | Compute the comparison in Python and return a reply beginning with `[DEMO]`. |
| `llm` | Configured | Return the provider's text without replacing or correcting it with a Python recommendation. |
| `llm` | None | Return HTTP `503` with `LLM provider is not configured.` |
| `demo` | Supplied | Reject the conflicting configuration with `ValueError`. |

`create_app(provider=provider, mode="llm")` remains the injection interface for tests. `create_configured_app()` reads the environment and builds the Gemini adapter only in LLM mode. Both `GEMINI_API_KEY` and `GEMINI_MODEL` must be nonblank; otherwise the LLM provider is unconfigured. App import and startup do not make a model request. `.env` files are not loaded automatically.

Timeouts return `504`. Connection failures, non-success upstream HTTP statuses, malformed responses, and unusable text return `502`. Gemini quota/rate-limit errors retain the upstream status number in the safe error detail, for example `Model provider returned HTTP 429.` The application does not retry automatically or fall back to the demo. Request/player validation still precedes the provider check (`422` for invalid input, `404` for unknown players).

## Try the demo

```powershell
$env:CHAT_MODE = "demo"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [the local API page](http://127.0.0.1:8000/docs) while the server is running. Expand **POST /chat**, select **Try it out**, and execute the following request.

```json
{
  "message": "Compare these players in PTS, REB, and TO.",
  "player_a": "donovan_mitchell",
  "player_b": "cade_cunningham"
}
```

The API returns HTTP `200` and a `reply` beginning with `[DEMO]`. Cunningham is recommended for this recorded snapshot because he has higher PTS and REB and the same TO. Stop the server with **Ctrl+C**.

Player selectors accept a stored ID or a full name, ignoring case and surrounding whitespace. The available IDs are `donovan_mitchell`, `cade_cunningham`, `cooper_flagg`, `jayson_tatum`, and `luka_doncic`. Requests that omit the player fields use Mitchell and Cunningham as defaults.

Unknown players return HTTP `404`. Selecting the same player twice returns `422`. A comparison with split category advantages explains the differences and asks for the category priority.

The local demo computes the comparison directly in Python. The free-text message is preserved in the user role for the LLM integration. The data snapshot is loaded when the application is created, so restart the server after editing the JSON file.


## Try the Gemini connection

The selected starting model is `gemini-3.5-flash-lite`. As checked on **20 November 2026**, Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing/#gemini-3.5-flash-lite) lists free-tier input and output for this model. Availability and quota depend on the project. Use a project marked **Free Tier**, with billing disabled, to preserve the no-spend requirement; a paid project's key can incur charges even for this model. See Google's [billing guide](https://ai.google.dev/gemini-api/docs/billing).

Create an API key in [Google AI Studio](https://aistudio.google.com/api-keys). Set it only in your own PowerShell session, using a hidden prompt rather than pasting the key into a command, chat, or repository:

```powershell
$taskGeminiKey = Read-Host 'Gemini API key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $taskGeminiKey).Password
Remove-Variable taskGeminiKey
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
$env:CHAT_MODE = "llm"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the same request as the demo at [the local API page](http://127.0.0.1:8000/docs). This time the reply comes from Gemini; its correctness must be reviewed. A normal text response also includes `model_metadata` with the requested model, returned model version, finish reason, token usage, and generation settings. No API key is included in messages, response metadata, or the provider object's representation.

The adapter uses the existing HTTPX dependency and Google's [generateContent REST API](https://ai.google.dev/api/generate-content). The trusted message becomes `systemInstruction`; user text stays in `contents` with the `user` role. Each request starts without previous conversation history. Settings are temperature `0`, maximum output `2048` tokens, and a `30`-second timeout for each HTTPX operation.

Nonblank text is preserved even when the finish reason is `MAX_TOKENS`; the returned finish reason lets the later experiment runner flag incomplete answers instead of losing potentially important output. Thought-tagged parts are excluded from the user-facing answer. A provider content-filter block is reported separately in the safe error detail and must not be counted as evidence that the system prompt resisted an attack. Automated evaluation and raw experiment records are still to be implemented before scored A/B runs.

Stop the server before switching modes, then restart it. To return to the demo, set `$env:CHAT_MODE = "demo"` before starting Uvicorn again.
