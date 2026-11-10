from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictStr

from app.messages import build_messages
from app.validation import validate_message

ChatProvider = Callable[[list[dict[str, str]]], str]


class ChatRequest(BaseModel):
    message: StrictStr


def demo_provider(_messages: list[dict[str, str]]) -> str:
    return (
        "[DEMO] In synthetic fixture F01, Player A leads in PTS (20 vs 18) "
        "and REB (8 vs 6), and has fewer turnovers (2 vs 3)."
    )


def create_app(provider: ChatProvider = demo_provider) -> FastAPI:
    application = FastAPI(title="NBA Fantasy Comparison Chatbot")

    @application.post("/chat")
    def chat(request: ChatRequest) -> dict[str, str]:
        try:
            message = validate_message(request.message)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        messages = build_messages(message)

        try:
            reply = provider(messages)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Model timed out.") from exc

        if not isinstance(reply, str) or not reply.strip():
            raise HTTPException(status_code=502, detail="Model returned an empty reply.")

        return {"reply": reply}

    return application


app = create_app()
