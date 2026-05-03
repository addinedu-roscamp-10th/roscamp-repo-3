import json
from datetime import date, datetime


def generated_at(clock):
    value = clock()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    return bool(value)


def optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bounded_int(value, *, default, minimum, maximum):
    numeric_value = optional_int(value)
    if numeric_value is None:
        numeric_value = default
    return max(minimum, min(numeric_value, maximum))


def optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_optional_text(value):
    text = str(value or "").strip()
    return text or None


def isoformat(value, *, none_value=None):
    if value in (None, ""):
        return none_value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


__all__ = [
    "bool_value",
    "bounded_int",
    "generated_at",
    "isoformat",
    "json_object",
    "normalize_optional_text",
    "optional_float",
    "optional_int",
]
