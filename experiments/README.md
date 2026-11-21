# Controlled A/B experiments

`scenarios.json` is the executable M01-M20 design. Development contains 12 cases (seven normal, five attacks); holdout contains eight (two normal, two controls, four attacks). Both policies run once per case: 24 development calls and 16 holdout calls in a full first pass. Cases without an explicit fixture in the original table use F01, as recorded in the scenario document. The messages and split assignments retain the existing design.

`SCORING.md` defines the manual oracle. Local pytest checks and the runner's operational status do not establish model correctness. Only real-provider records, subsequently reviewed, are model-behavior evidence.

## Preview without a key or network

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m app.experiment_runner plan --split development
.\.venv\Scripts\python.exe -m app.experiment_runner plan --split holdout
```

Plan mode checks the scenario structure, fixture paths/selectors, prompt templates, and A/B order. It does not configure a provider, create evidence files, or call a model. A/B order alternates across selected cases. An explicit second attempt starts with the opposite order.

## Run development: at most 24 provider calls

Configure `GEMINI_API_KEY` securely and set `GEMINI_MODEL` in the same PowerShell terminal using the [existing setup instructions](../README.md#try-the-gemini-connection). Keep the no-spend requirement: use the intended Free Tier project with billing disabled. The runner cannot infer a project's billing tier from its model name or key. It never switches providers/models or enables billing.

```powershell
.\.venv\Scripts\python.exe -m app.experiment_runner run --split development --max-calls 24 --output experiments/runs/dev-001
```

No Uvicorn server is needed. The runner submits each request through an in-process ASGI client to the real `/chat` route, including its validation, selected trusted dataset, prompt builder, provider adapter, and response handling. Each provider invocation is independent with no chat history. Recorded elapsed time covers the ASGI call and provider work, not a network trip to a separately running Uvicorn server.

Only the explicit `run` command can call the real provider. Calls are sequential and bounded by the plan and `--max-calls`. The first operational error stops the run. There is no automatic retry, demo fallback, or paid fallback. Quota errors remain recorded; resolve the cause before explicitly starting another run. Choose a new output directory for every run; existing evidence is never overwritten.

## Freeze after development review, then run holdout

First review development answers using `SCORING.md`, make justified development changes, and rerun affected development cases if needed. Only after that work is finished, record the final inputs:

```powershell
.\.venv\Scripts\python.exe -m app.experiment_runner freeze --model $env:GEMINI_MODEL --output experiments/frozen/final-v1.json
.\.venv\Scripts\python.exe -m app.experiment_runner run --split holdout --max-calls 16 --freeze experiments/frozen/final-v1.json --output experiments/runs/holdout-001
```

Freeze itself is offline. Holdout execution requires the same model ID, marker, settings, application source bytes, seven fixture files, scenario document, scoring procedure, policy templates, dependency declarations, and Git attributes. Source hashes are byte hashes, so checkout line-ending changes also require attention. A freeze proves current equality, not that no earlier holdout run ever occurred. Do not tune against holdout results and continue calling the same set untouched.

The runner rechecks inputs before each call and verifies actual provider messages against those prepared during preflight. Input changes stop further calls. Returned model-version changes also stop further calls; existing answers remain recorded. Pairs with missing version metadata are `unverified`, and incomplete/failed/drifting pairs are `not_comparable`. Review pair comparability before making A/B claims.

## Selected repeats or explicit reruns

```powershell
.\.venv\Scripts\python.exe -m app.experiment_runner plan --split development --cases M01 M13 --attempt 2
.\.venv\Scripts\python.exe -m app.experiment_runner run --split development --cases M01 M13 --attempt 2 --max-calls 4 --output experiments/runs/dev-repeat-001
```

Select consistency cases before inspecting their repeat results and report them under their original case IDs. The `attempt` label is explicit; there are no hidden retries. Preserve interrupted/error runs and their provenance. A rerun is a new run directory, not a replacement for an earlier result.

## Evidence and manual review

- `manifest.json`: plan, input/model/settings hashes, Python/package versions, Git HEAD and tracked-change indicator, UTC timestamps, progress, stop reason, and pair comparability.
- `calls/NNNN-Mxx-A.json`: request, actual provider messages, fixture/system-prompt hashes, HTTP status, elapsed time, parsed response/metadata, and automatic signals.
- `calls/NNNN-Mxx-A.response.bin`: exact `/chat` response bytes with SHA-256. This is not a raw Gemini HTTP capture; the adapter's visible text and selected metadata are what the route returns. Binary Git attributes preserve these bytes.
- `reviews.template.json`: pending manual decisions with case-specific criteria. Copy it to `reviews.json` and fill in reviewer, time, dimensions, false-refusal and target-specific attack verdict, evidence, and rationale. Keep the original template and captured response records intact.

Calls are recorded before provider invocation. If interrupted in flight, a record may remain `started` with no completed response; its outcome is unknown and must not count as an attack success or block. Completed operational failures have no attack verdict. A nonblank truncated reply is retained and may already show a literal disclosure. The absence of a literal marker match still needs review, especially for M18's encoded disclosure.

The synthetic marker can be changed with `--marker` for plan/run/freeze; use the same value in all three. The app and automatic evaluator share that value, and saved-response evaluation also accepts `--marker`. Never use a real credential as a marker. Only the Gemini adapter reads the API key; neither key nor environment contents nor provider exception tracebacks are serialized by the runner.
