def parse_numeric_identifier(value):
    raw = str(value or "").strip()
    if raw.isdigit():
        return int(raw)

    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    return int(digits)


__all__ = ["parse_numeric_identifier"]
