# Trusted synthetic player fixtures

F01-F07 are the synthetic per-game examples defined in [the test design](../../testdesign.md#4-test-data-and-comparison-oracle). They are not NBA statistics. `S1` is a shared synthetic season window and `L5` is a different five-game window. The `as_of_date` records fixture preparation, not a real statistics retrieval.

Load a fixture through server-side Python configuration:

```python
from pathlib import Path

from app.main import create_app
from app.players import load_dataset

dataset = load_dataset(Path("experiments/fixtures/F04.json"))
application = create_app(provider=provider, mode="llm", dataset=dataset)
```

Here `provider` is an explicitly configured provider callable. Creating the application does not call it. The application copies the dataset at creation, so later changes to the caller's dictionaries do not change an active experiment. An application without the `dataset` argument continues to load the fixed NBA snapshot.

Send requests to that application's `/chat` endpoint with `player_a: "player_a"` and `player_b: "player_b"`. The ordinary endpoint defaults still name Mitchell and Cunningham; they are not aliases for synthetic players. `dataset`, a fixture path, a marker, and a prompt variant are not accepted request-body fields. Extra fields receive HTTP `422` before a provider call.

Each selected row inherits a common dataset period, season, season type, and statistical basis unless the row provides its own value. Row metadata overrides the dataset's common metadata. F04 intentionally has a null TO value and F05 intentionally gives Player B period `L5` instead of `S1`. Demo mode withholds a full recommendation in those cases. LLM mode sends the selected records and metadata to the provider unchanged, so the experiment can measure whether the model notices missing or incompatible data.

For M07, keep the API selectors at `player_a` and `player_b` and ask about the absent Player C in the free-text message. Setting a selector to `player_c` would produce an application-level `404` and skip the model, which cannot establish the model's response to missing player data.

The fixture API tests use stubs for A and B and establish routing, data isolation, and role boundaries. They do not establish real-model correctness or attack resistance. Prompt text, fixture values, and the scoring procedure must be frozen before the final holdout evaluation.
