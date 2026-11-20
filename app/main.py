import json
import os
from collections.abc import Callable
from hashlib import sha256

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictStr

from app.comparison import compare_players
from app.gemini import ProviderError, ProviderReply, gemini_provider_from_env
from app.messages import build_messages, validate_prompt_variant
from app.players import find_player, load_dataset
from app.validation import validate_message

ChatProvider = Callable[[list[dict[str, str]]], str | ProviderReply]


class ChatRequest(BaseModel):
    message: StrictStr
    player_a: StrictStr = "donovan_mitchell"
    player_b: StrictStr = "cade_cunningham"


def create_app(
    provider: ChatProvider | None = None,
    *,
    mode: str = "demo",
    prompt_variant: str = "A",
) -> FastAPI:
    validate_prompt_variant(prompt_variant)
    if mode not in {"demo", "llm"}:
        raise ValueError("Mode must be 'demo' or 'llm'.")
    if mode == "demo" and provider is not None:
        raise ValueError("Demo mode does not accept a provider. Use mode='llm'.")

    application = FastAPI(title="NBA Fantasy Comparison Chatbot")
    dataset = load_dataset()

    @application.post("/chat")
    def chat(request: ChatRequest) -> dict[str, object]:
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

        if mode == "llm" and provider is None:
            raise HTTPException(status_code=503, detail="LLM provider is not configured.")

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
        messages = build_messages(message, context, variant=prompt_variant)

        try:
            if mode == "demo":
                reply = compare_players(first, second)
            else:
                reply = provider(messages)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Model timed out.") from exc
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        metadata = None
        if isinstance(reply, ProviderReply):
            metadata = reply.metadata
            reply = reply.text

        if not isinstance(reply, str) or not reply.strip():
            raise HTTPException(status_code=502, detail="Model returned an empty reply.")

        result: dict[str, object] = {"reply": reply}
        if metadata is not None:
            result["model_metadata"] = {
                **metadata,
                "prompt_variant": prompt_variant,
                "system_prompt_sha256": sha256(messages[0]["content"].encode("utf-8")).hexdigest(),
            }
        return result

    return application


def create_configured_app() -> FastAPI:
    mode = os.environ.get("CHAT_MODE", "demo")
    provider = gemini_provider_from_env() if mode == "llm" else None
    return create_app(provider, mode=mode, prompt_variant=os.environ.get("PROMPT_VARIANT", "A"))


app = create_configured_app()
