import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "players.json"


def load_dataset(path: str | Path | None = None) -> dict:
    source = DATA_PATH if path is None else Path(path)
    return json.loads(source.read_text(encoding="utf-8-sig"))


def find_player(dataset: dict, selector: str) -> dict:
    normalized = selector.strip().casefold()

    for player in dataset["players"]:
        if normalized in (player["id"].casefold(), player["name"].casefold()):
            return player

    raise ValueError(f"Player not found: {selector}")
