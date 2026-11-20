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

The suite defines 26 test cases, with 17 unit cases and nine API integration cases. The last user-verified baseline was 23 passed on 20 November 2026; the three new mode cases require a fresh run before recording a new pass count. The unit cases cover message validation, message roles, player lookup, comparison rules, and invalid mode configurations. The API cases cover provider responses and errors, the unconfigured LLM mode, player selection, unknown players, duplicate selections, and the selected data sent to the provider. The case-to-rule and technique mapping, including planned tests that are still missing, is in [the test design](testdesign.md#6-local-test-inventory-and-implementation-status).

The tests use controlled provider stubs and a deterministic local comparison. Real-model prompt injection and jailbreak evaluation is planned in [the test design](testdesign.md).

## Working modes

`CHAT_MODE` selects the mode when Uvicorn imports `app.main:app`. The default is `demo`. An unknown mode fails at application creation.

| Mode | Provider | Behavior for a valid comparison |
| --- | --- | --- |
| `demo` | None | Compute the comparison in Python and return a reply beginning with `[DEMO]`. |
| `llm` | Configured | Return the provider's reply without replacing it with a Python recommendation. |
| `llm` | None | Return HTTP `503` with `LLM provider is not configured.` |
| `demo` | Supplied | Reject the conflicting configuration with `ValueError`. |

Code that injects a provider must select the mode explicitly: `create_app(provider=provider, mode="llm")`. Tests use this interface with controlled stubs. A real provider adapter and its credentials are not implemented yet, so setting `CHAT_MODE` to `llm` alone does not connect a model.

In LLM mode, timeouts return `504`, and blank or non-string replies return `502`. These outcomes never fall back to the demo. General upstream error mapping is still planned. Request and player validation happen before the provider-configuration check, so invalid input returns `422`, and unknown players return `404` even when the LLM provider is missing.

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

The local demo computes the comparison directly in Python. The free-text message is preserved in the user role for the future model integration. The data snapshot is loaded when the application is created, so restart the server after editing the JSON file.
