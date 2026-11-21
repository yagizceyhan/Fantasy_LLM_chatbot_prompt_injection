"""Verify stored smoke-evidence bytes without making a model request."""

import json
from hashlib import sha256
from pathlib import Path


EVIDENCE_DIR = (
    Path(__file__).resolve().parents[1]
    / "experiments/manual/2026-11-20-smoke-001"
)


def main() -> int:
    provenance = json.loads(
        (EVIDENCE_DIR / "provenance.json").read_text(encoding="utf-8-sig")
    )
    checks = (
        ("response.user-paste.txt", "user_paste_sha256"),
        ("response.json", "normalized_response_sha256"),
        ("response.screenshot.png", "source_screenshot_sha256"),
    )
    failed = False
    for filename, field in checks:
        actual = sha256((EVIDENCE_DIR / filename).read_bytes()).hexdigest()
        matches = actual == provenance[field]
        print(f"{'PASS' if matches else 'FAIL'} {filename}: {actual}")
        failed |= not matches

    messages = json.loads(
        (EVIDENCE_DIR / "messages.reconstructed.json").read_text(encoding="utf-8-sig")
    )
    actual = sha256(messages[0]["content"].encode("utf-8")).hexdigest()
    matches = actual == provenance["reconstructed_system_prompt_sha256"]
    print(f"{'PASS' if matches else 'FAIL'} reconstructed system prompt: {actual}")
    failed |= not matches

    print("Historical source-code and dataset hashes are not current-checkout assertions.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
