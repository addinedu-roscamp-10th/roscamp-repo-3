import os
from dataclasses import dataclass


DEFAULT_PATROL_MAP_ID = "map_0504"


@dataclass(frozen=True)
class PatrolRuntimeConfig:
    pinky_id: str = "pinky3"
    map_id: str = DEFAULT_PATROL_MAP_ID
    patrol_timeout_sec: int = 180


def get_patrol_runtime_config() -> PatrolRuntimeConfig:
    return PatrolRuntimeConfig(
        pinky_id=os.getenv("PATROL_PINKY_ID", "pinky3").strip() or "pinky3",
        map_id=os.getenv("ROPI_PATROL_MAP_ID", DEFAULT_PATROL_MAP_ID).strip()
        or DEFAULT_PATROL_MAP_ID,
        patrol_timeout_sec=int(os.getenv("PATROL_PATH_TIMEOUT_SEC", "180") or "180"),
    )


__all__ = ["DEFAULT_PATROL_MAP_ID", "PatrolRuntimeConfig", "get_patrol_runtime_config"]
