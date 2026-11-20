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

The suite contains 23 test cases, with 15 unit cases and eight API integration cases. The unit cases cover message validation, message roles, player lookup, and comparison rules. The API cases cover provider responses and errors, player selection, unknown players, duplicate selections, and the selected data sent to the provider.

The tests use controlled provider stubs and a deterministic local comparison. Real-model prompt injection and jailbreak evaluation is planned in [the test design](testdesign.md).

## Try the demo

```powershell
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
