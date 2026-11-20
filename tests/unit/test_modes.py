import pytest

from app.main import create_app


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="Mode must be"):
        create_app(mode="unknown")


def test_demo_mode_rejects_provider():
    def provider(_messages):
        pytest.fail("A provider must not be called in demo mode.")

    with pytest.raises(ValueError, match="Demo mode does not accept a provider"):
        create_app(provider, mode="demo")
