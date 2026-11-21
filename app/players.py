import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "players.json"


def load_dataset(path: str | Path | None = None) -> dict:
    source = DATA_PATH if path is None else Path(path)
    return json.loads(source.read_text(encoding="utf-8-sig"))


def build_player_context(dataset: dict, first: dict, second: dict) -> str:
    context = {
        "as_of_date": dataset["as_of_date"],
        "season": dataset["season"],
        "season_type": dataset["season_type"],
        "stat_basis": dataset["stat_basis"],
        "players": [first, second],
    }
    for key in ("fixture_id", "period"):
        if key in dataset:
            context[key] = dataset[key]
    return json.dumps(context, ensure_ascii=False)


def find_player(dataset: dict, selector: str) -> dict:
    normalized = selector.strip().casefold()

    for player in dataset["players"]:
        if normalized in (player["id"].casefold(), player["name"].casefold()):
            return player

    raise ValueError(f"Player not found: {selector}")
