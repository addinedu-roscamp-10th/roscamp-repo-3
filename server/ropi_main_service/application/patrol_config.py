import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PatrolRuntimeConfig:
    pinky_id: str = "pinky3"
    patrol_timeout_sec: int = 180


def get_patrol_runtime_config() -> PatrolRuntimeConfig:
    return PatrolRuntimeConfig(
        pinky_id=os.getenv("PATROL_PINKY_ID", "pinky3").strip() or "pinky3",
        patrol_timeout_sec=int(os.getenv("PATROL_PATH_TIMEOUT_SEC", "180") or "180"),
    )


__all__ = ["PatrolRuntimeConfig", "get_patrol_runtime_config"]
