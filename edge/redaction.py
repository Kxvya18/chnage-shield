import re

SECRET_KEY_PATTERN = re.compile(r"password|secret|token|authorization|cookie|api[_-]?key", re.I)
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]+=*", re.I)


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if SECRET_KEY_PATTERN.search(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    return value

