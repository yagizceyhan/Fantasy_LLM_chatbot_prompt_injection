import json
from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictStr

from app.comparison import compare_players
from app.messages import build_messages
from app.players import find_player, load_dataset
from app.validation import validate_message

ChatProvider = Callable[[list[dict[str, str]]], str]


class ChatRequest(BaseModel):
    message: StrictStr
    player_a: StrictStr = "donovan_mitchell"
    player_b: StrictStr = "cade_cunningham"


def create_app(provider: ChatProvider | None = None) -> FastAPI:
    application = FastAPI(title="NBA Fantasy Comparison Chatbot")
    dataset = load_dataset()

    @application.post("/chat")
    def chat(request: ChatRequest) -> dict[str, str]:
        try:
            message = validate_message(request.message)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            first = find_player(dataset, request.player_a)
            second = find_player(dataset, request.player_b)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if first["id"] == second["id"]:
            raise HTTPException(status_code=422, detail="Choose two different players.")

        context = json.dumps(
            {
                "as_of_date": dataset["as_of_date"],
                "season": dataset["season"],
                "season_type": dataset["season_type"],
                "stat_basis": dataset["stat_basis"],
                "players": [first, second],
            },
            ensure_ascii=False,
        )
        messages = build_messages(message, context)

        try:
            if provider is None:
                reply = compare_players(first, second)
            else:
                reply = provider(messages)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Model timed out.") from exc

        if not isinstance(reply, str) or not reply.strip():
            raise HTTPException(status_code=502, detail="Model returned an empty reply.")

        return {"reply": reply}

    return application


app = create_app()
