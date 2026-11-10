import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_valid_request_returns_provider_reply():
    calls = []

    def provider(messages):
        calls.append(messages)
        return "Expected provider reply."

    with TestClient(create_app(provider)) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 200
    assert response.json() == {"reply": "Expected provider reply."}
    assert len(calls) == 1
    assert calls[0][-1] == {"role": "user", "content": "Compare A and B."}


def test_missing_message_skips_provider():
    def provider(_messages):
        pytest.fail("The provider should not receive an invalid request.")

    with TestClient(create_app(provider)) as client:
        response = client.post("/chat", json={})

    assert response.status_code == 422


def test_provider_timeout_returns_504():
    def provider(_messages):
        raise TimeoutError

    with TestClient(create_app(provider)) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 504


def test_blank_provider_reply_returns_502():
    def provider(_messages):
        return " \t "

    with TestClient(create_app(provider)) as client:
        response = client.post("/chat", json={"message": "Compare A and B."})

    assert response.status_code == 502
