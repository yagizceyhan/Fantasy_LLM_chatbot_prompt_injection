import pytest

from app.validation import validate_message


def test_accepts_one_character():
    assert validate_message("x") == "x"


def test_rejects_empty_message():
    with pytest.raises(ValueError):
        validate_message("")


def test_accepts_maximum_length():
    message = "x" * 2000
    assert validate_message(message) == message


def test_rejects_overlong_message_before_trimming():
    with pytest.raises(ValueError):
        validate_message("x" * 2000 + " ")
