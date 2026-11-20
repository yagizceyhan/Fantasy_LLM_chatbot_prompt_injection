import pytest
from fastapi.testclient import TestClient

from app.gemini import ProviderError, ProviderReply
from app.main import create_app, create_configured_app


def test_valid_request_returns_provider_reply():
    calls = []

    def provider(messages):
        calls.append(messages)
        return "Expected provider reply."

    with TestClient(create_app(provider, mode="llm")) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 200
    assert response.json() == {"reply": "Expected provider reply."}
    assert len(calls) == 1
    assert calls[0][-1] == {"role": "user", "content": "Compare A and B."}


def test_missing_message_skips_provider():
    def provider(_messages):
        pytest.fail("The provider should not receive an invalid request.")

    with TestClient(create_app(provider, mode="llm")) as client:
        response = client.post("/chat", json={})

    assert response.status_code == 422


def test_provider_timeout_returns_504():
    def provider(_messages):
        raise TimeoutError

    with TestClient(create_app(provider, mode="llm")) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 504


def test_blank_provider_reply_returns_502():
    def provider(_messages):
        return " \t "

    with TestClient(create_app(provider, mode="llm")) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 502


def test_unconfigured_provider_returns_503():
    with TestClient(create_app(mode="llm")) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 503
    assert response.json() == {"detail": "LLM provider is not configured."}


def test_upstream_error_returns_502():
    def provider(_messages):
        raise ProviderError("Model provider returned HTTP 429.")

    with TestClient(create_app(provider, mode="llm")) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 502
    assert response.json() == {"detail": "Model provider returned HTTP 429."}


def test_llm_environment_returns_provider_text_and_metadata(monkeypatch):
    calls = []
    metadata = {"provider": "gemini", "model_version": "synthetic-model-version"}

    def provider(messages):
        calls.append(messages)
        return ProviderReply(text="Unmodified model answer.", metadata=metadata)

    monkeypatch.setenv("CHAT_MODE", "llm")
    monkeypatch.setattr("app.main.gemini_provider_from_env", lambda: provider)
    with TestClient(create_configured_app()) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 200
    assert response.json() == {"reply": "Unmodified model answer.", "model_metadata": metadata}
    assert len(calls) == 1
    assert calls[0][0]["role"] == "system"
    assert calls[0][1] == {"role": "user", "content": "Compare A and B."}
