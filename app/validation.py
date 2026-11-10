MAX_MESSAGE_LENGTH = 2000


def validate_message(message: object) -> str:
    if not isinstance(message, str):
        raise ValueError("Message must be a string.")

    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError("Message must be at most 2000 characters.")

    if not message.strip():
        raise ValueError("Message must contain non-whitespace text.")

    return message
