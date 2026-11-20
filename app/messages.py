from pathlib import Path

TEST_MARKER = "CMPE411-SYNTHETIC-F01-93"
FIXTURE_F01 = """Synthetic per-game averages for the same period (S1).
Player A: PTS 20, REB 8, TO 2.
Player B: PTS 18, REB 6, TO 3."""



PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_VARIANTS = ("A", "B")


def validate_prompt_variant(variant: str) -> None:
    if variant not in PROMPT_VARIANTS:
        raise ValueError("Prompt variant must be 'A' or 'B'.")


def build_messages(
    message: str,
    player_context: str = FIXTURE_F01,
    *,
    variant: str = "A",
    marker: str = TEST_MARKER,
) -> list[dict[str, str]]:
    validate_prompt_variant(variant)
    if not isinstance(marker, str) or not marker.strip():
        raise ValueError("A nonblank synthetic marker is required.")
    template = (PROMPT_DIR / f"policy_{variant.lower()}.txt").read_text(encoding="utf-8")
    system_prompt = template.format(player_context=player_context, test_marker=marker)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]
