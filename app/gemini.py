import os
import re
from dataclasses import dataclass, field

import httpx


class ProviderError(RuntimeError):
    """An upstream failure with a safe, application-controlled message."""


@dataclass(frozen=True)
class ProviderReply:
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class GeminiProvider:
    api_key: str = field(repr=False)
    model: str
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    def __post_init__(self):
        if not self.api_key.strip():
            raise ValueError("A Gemini API key is required.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise ValueError("Use a Gemini model ID without a path or URL.")

    def __call__(self, messages: list[dict[str, str]]) -> ProviderReply:
        if len(messages) != 2 or [item["role"] for item in messages] != ["system", "user"]:
            raise ValueError("Gemini requires one system message and one user message.")

        payload = {
            "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 2048},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        try:
            with httpx.Client(timeout=30.0, transport=self.transport) as client:
                response = client.post(url, headers={"x-goog-api-key": self.api_key}, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("Gemini request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Model provider returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Model provider request failed.") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("Model provider returned invalid JSON.") from exc

        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            if not isinstance(parts, list):
                raise TypeError
            text_parts = []
            for part in parts:
                if part.get("thought"):
                    continue
                if "text" in part:
                    if not isinstance(part["text"], str):
                        raise TypeError
                    text_parts.append(part["text"])
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            feedback = data.get("promptFeedback", {}) if isinstance(data, dict) else {}
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                raise ProviderError("Model provider blocked the request.") from exc
            raise ProviderError("Model provider returned an invalid response.") from exc

        reply = "".join(text_parts)
        if not reply.strip():
            raise ProviderError("Model provider returned an empty text reply.")

        return ProviderReply(
            text=reply,
            metadata={
                "provider": "gemini",
                "requested_model": self.model,
                "model_version": data.get("modelVersion"),
                "finish_reason": candidate.get("finishReason"),
                "usage": data.get("usageMetadata", {}),
                "temperature": 0,
                "max_output_tokens": 2048,
            },
        )


def gemini_provider_from_env() -> GeminiProvider | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if not api_key or not model:
        return None
    return GeminiProvider(api_key=api_key, model=model)
