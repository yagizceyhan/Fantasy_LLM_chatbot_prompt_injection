# NBA Fantasy Chatbot Security Tests

CMPE 411 project on prompt injection and jailbreak testing for an H2H 9-cat NBA Fantasy chatbot. The first version compares points, rebounds, and turnovers using a synthetic fixture and a fixed demo reply.

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
.\.venv\Scripts\python.exe -m pytest -q
```

The initial suite has six unit tests and four API integration tests. The unit tests cover message length and the separation of system and user messages. The API tests cover a successful request, a missing message, a provider timeout, and an empty provider reply. Use `-v` in place of `-q` to see each test name and result.

## Try the demo

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [the local API page](http://127.0.0.1:8000/docs) while the server is running. Expand **POST /chat**, select **Try it out**, and execute the following request.

```json
{
  "message": "Compare A and B in PTS, REB, and TO."
}
```

The API returns HTTP `200` and a `reply` beginning with `[DEMO]`. The reply describes Player A's advantages in synthetic fixture F01. Stop the server with **Ctrl+C**.

The demo and the automated suite use local provider stubs. The [test design](testdesign.md) describes the planned evaluation with a real language model.
