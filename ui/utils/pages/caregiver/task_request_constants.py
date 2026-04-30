PRIORITY_LABEL_TO_CODE = {
    "일반": "NORMAL",
    "긴급": "URGENT",
    "최우선": "HIGHEST",
}

PRIORITY_CODE_TO_LABEL = {
    code: label
    for label, code in PRIORITY_LABEL_TO_CODE.items()
}


__all__ = [
    "PRIORITY_CODE_TO_LABEL",
    "PRIORITY_LABEL_TO_CODE",
]
