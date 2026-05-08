import os


MANIPULATION_ACTION_TIMEOUT_ENV = "ROPI_MANIPULATION_ACTION_TIMEOUT_SEC"
DEFAULT_MANIPULATION_ACTION_TIMEOUT_SEC = 90.0


def get_manipulation_action_timeout_sec(
    *, default: float = DEFAULT_MANIPULATION_ACTION_TIMEOUT_SEC
) -> float:
    raw = str(os.getenv(MANIPULATION_ACTION_TIMEOUT_ENV, "")).strip()
    if not raw:
        return float(default)

    try:
        timeout_sec = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{MANIPULATION_ACTION_TIMEOUT_ENV}는 숫자여야 합니다.") from exc

    if timeout_sec <= 0:
        raise RuntimeError(f"{MANIPULATION_ACTION_TIMEOUT_ENV}는 0보다 커야 합니다.")
    return timeout_sec


__all__ = [
    "DEFAULT_MANIPULATION_ACTION_TIMEOUT_SEC",
    "MANIPULATION_ACTION_TIMEOUT_ENV",
    "get_manipulation_action_timeout_sec",
]
