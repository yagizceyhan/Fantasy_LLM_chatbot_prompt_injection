def compare_players(first: dict, second: dict) -> str:
    categories = (("pts", True), ("reb", True), ("to", False))

    for player in (first, second):
        missing = [key.upper() for key, _ in categories if player.get(key) is None]
        if missing:
            return (
                f"[DEMO] Missing statistics for {player['name']}: "
                f"{', '.join(missing)}. Please provide the missing data."
            )

    for key, label in (
        ("period", "periods"),
        ("season", "seasons"),
        ("season_type", "season types"),
        ("stat_basis", "statistical bases"),
    ):
        if first.get(key) != second.get(key):
            return (
                f"[DEMO] Incompatible {label}: {first.get(key)!r} vs "
                f"{second.get(key)!r}. Please provide data for the same period "
                "and statistical basis before a full comparison."
            )

    first_advantages = []
    second_advantages = []
    lines = ["[DEMO] Comparison of the recorded per-game averages."]

    for key, higher_is_better in categories:
        left = first[key]
        right = second[key]
        description = f"{key.upper()}: {first['name']} {left} vs {second['name']} {right}."

        if left == right:
            lines.append(f"{description} Tie.")
            continue

        first_is_better = (left > right) == higher_is_better
        if first_is_better:
            winner = first["name"]
            first_advantages.append(key)
        else:
            winner = second["name"]
            second_advantages.append(key)

        lines.append(f"{description} Advantage: {winner}.")

    if not first_advantages and not second_advantages:
        lines.append("The players are tied in PTS, REB, and TO.")
    elif not second_advantages:
        lines.append(f"Recommendation: {first['name']}.")
    elif not first_advantages:
        lines.append(f"Recommendation: {second['name']}.")
    else:
        lines.append("Both players have advantages. Which category matters most to you?")

    return " ".join(lines)
