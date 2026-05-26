import os
from dataclasses import dataclass


DEFAULT_DRIVE_MAP_ID = "map_0504"
DEFAULT_DRIVE_ROBOT_IDS = ("pinky1", "pinky3")


@dataclass(frozen=True)
class DriveRuntimeConfig:
    map_id: str = DEFAULT_DRIVE_MAP_ID
    robot_ids: tuple[str, ...] = DEFAULT_DRIVE_ROBOT_IDS

    def is_robot_allowed(self, robot_id: str) -> bool:
        return robot_id in self.robot_ids


def get_drive_runtime_config() -> DriveRuntimeConfig:
    raw_robot_ids = os.getenv("ROPI_DRIVE_ROBOT_IDS", "").strip()
    if raw_robot_ids:
        robot_ids = tuple(
            robot_id.strip()
            for robot_id in raw_robot_ids.split(",")
            if robot_id.strip()
        )
    else:
        robot_ids = DEFAULT_DRIVE_ROBOT_IDS

    map_id = os.getenv("ROPI_FMS_MAP_ID", DEFAULT_DRIVE_MAP_ID).strip()
    return DriveRuntimeConfig(
        map_id=map_id or DEFAULT_DRIVE_MAP_ID,
        robot_ids=robot_ids or DEFAULT_DRIVE_ROBOT_IDS,
    )


__all__ = [
    "DEFAULT_DRIVE_MAP_ID",
    "DEFAULT_DRIVE_ROBOT_IDS",
    "DriveRuntimeConfig",
    "get_drive_runtime_config",
]
