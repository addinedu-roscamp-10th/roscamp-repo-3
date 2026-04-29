import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from server.ropi_main_service.application.goal_pose import (
    normalize_goal_pose_spec,
    parse_goal_pose_map_string,
    parse_goal_pose_string,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")


DEFAULT_DELIVERY_PINKY_ID = "pinky2"
DEFAULT_DELIVERY_PICKUP_ARM_ID = "arm1"
DEFAULT_DELIVERY_DESTINATION_ARM_ID = "arm2"
DEFAULT_DELIVERY_PICKUP_ARM_ROBOT_ID = "jetcobot1"
DEFAULT_DELIVERY_DESTINATION_ARM_ROBOT_ID = "jetcobot2"
DEFAULT_DELIVERY_ROBOT_SLOT_ID = "robot_slot_a1"
DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC = 120.0
DEFAULT_DELIVERY_GOAL_POSE_SOURCE = "db"
DEFAULT_DELIVERY_PICKUP_GOAL_POSE_ID = "pickup_supply"
DEFAULT_DELIVERY_RETURN_TO_DOCK_GOAL_POSE_ID = "dock_home"


@dataclass(frozen=True)
class DeliveryRuntimeConfig:
    pinky_id: str = DEFAULT_DELIVERY_PINKY_ID
    pickup_arm_id: str = DEFAULT_DELIVERY_PICKUP_ARM_ID
    destination_arm_id: str = DEFAULT_DELIVERY_DESTINATION_ARM_ID
    pickup_arm_robot_id: str = DEFAULT_DELIVERY_PICKUP_ARM_ROBOT_ID
    destination_arm_robot_id: str = DEFAULT_DELIVERY_DESTINATION_ARM_ROBOT_ID
    robot_slot_id: str = DEFAULT_DELIVERY_ROBOT_SLOT_ID
    navigation_timeout_sec: float = DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC

    @property
    def arm_ids(self) -> tuple[str, ...]:
        return (self.pickup_arm_id, self.destination_arm_id)


def _load_text_env(name: str, *, default: str) -> str:
    value = str(os.getenv(name, default)).strip()
    if not value:
        return default
    return value


def _load_float_env(name: str, *, default: float) -> float:
    raw = str(os.getenv(name, str(default))).strip()
    if not raw:
        return default

    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name}는 숫자여야 합니다.") from exc


def get_delivery_runtime_config() -> DeliveryRuntimeConfig:
    return DeliveryRuntimeConfig(
        pinky_id=_load_text_env("ROPI_DELIVERY_PINKY_ID", default=DEFAULT_DELIVERY_PINKY_ID),
        pickup_arm_id=_load_text_env("ROPI_DELIVERY_PICKUP_ARM_ID", default=DEFAULT_DELIVERY_PICKUP_ARM_ID),
        destination_arm_id=_load_text_env(
            "ROPI_DELIVERY_DESTINATION_ARM_ID",
            default=DEFAULT_DELIVERY_DESTINATION_ARM_ID,
        ),
        pickup_arm_robot_id=_load_text_env(
            "ROPI_DELIVERY_PICKUP_ARM_ROBOT_ID",
            default=DEFAULT_DELIVERY_PICKUP_ARM_ROBOT_ID,
        ),
        destination_arm_robot_id=_load_text_env(
            "ROPI_DELIVERY_DESTINATION_ARM_ROBOT_ID",
            default=DEFAULT_DELIVERY_DESTINATION_ARM_ROBOT_ID,
        ),
        robot_slot_id=_load_text_env("ROPI_DELIVERY_ROBOT_SLOT_ID", default=DEFAULT_DELIVERY_ROBOT_SLOT_ID),
        navigation_timeout_sec=_load_float_env(
            "ROPI_DELIVERY_NAVIGATION_TIMEOUT_SEC",
            default=DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC,
        ),
    )


def _load_json_env(name: str, *, default):
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name}는 JSON 형식이어야 합니다.") from exc


def _load_raw_env(name: str) -> str:
    return str(os.getenv(name, "")).strip()


def get_delivery_navigation_config(*, repository=None, source=None) -> dict:
    normalized_source = str(
        source
        or os.getenv("ROPI_DELIVERY_GOAL_POSE_SOURCE")
        or DEFAULT_DELIVERY_GOAL_POSE_SOURCE
    ).strip().lower()

    if normalized_source == "env":
        return _get_delivery_navigation_config_from_env()
    if normalized_source == "db":
        return _get_delivery_navigation_config_from_db(repository=repository)

    raise RuntimeError(
        "ROPI_DELIVERY_GOAL_POSE_SOURCE는 'db' 또는 'env'여야 합니다."
    )


def _get_delivery_navigation_config_from_db(*, repository=None) -> dict:
    if repository is None:
        from server.ropi_main_service.persistence.repositories.task_request_repository import (
            DeliveryRequestRepository,
        )

        repository = DeliveryRequestRepository()

    return _build_delivery_navigation_config_from_db_rows(
        repository.get_enabled_goal_poses()
    )


def _build_delivery_navigation_config_from_db_rows(rows) -> dict:
    pickup_goal_pose = None
    return_to_dock_goal_pose = None
    destination_goal_poses = {}

    for row in rows or []:
        purpose = str(row.get("purpose") or "").upper()
        goal_pose_id = str(row.get("goal_pose_id") or "").strip()
        if not goal_pose_id:
            continue

        goal_pose = _build_goal_pose_from_db_row(row)
        if (
            purpose == "PICKUP"
            and goal_pose_id == DEFAULT_DELIVERY_PICKUP_GOAL_POSE_ID
        ):
            pickup_goal_pose = goal_pose
            continue

        if purpose == "DESTINATION":
            destination_goal_poses[goal_pose_id] = goal_pose
            continue

        if (
            purpose == "DOCK"
            and goal_pose_id == DEFAULT_DELIVERY_RETURN_TO_DOCK_GOAL_POSE_ID
        ):
            return_to_dock_goal_pose = goal_pose

    return {
        "pickup_goal_pose": pickup_goal_pose,
        "destination_goal_poses": destination_goal_poses,
        "return_to_dock_goal_pose": return_to_dock_goal_pose,
    }


def _build_goal_pose_from_db_row(row: dict) -> dict:
    goal_pose_id = str(row.get("goal_pose_id") or "").strip() or "unknown"
    return normalize_goal_pose_spec(
        {
            "x": row.get("pose_x"),
            "y": row.get("pose_y"),
            "yaw": row.get("pose_yaw"),
            "frame_id": row.get("frame_id") or "map",
        },
        env_name=f"goal_pose[{goal_pose_id}]",
    )


def _get_delivery_navigation_config_from_env() -> dict:
    pickup_goal_pose_json_raw = _load_json_env(
        "ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON",
        default=None,
    )
    destination_goal_poses_json_raw = _load_json_env(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON",
        default={},
    )
    return_to_dock_goal_pose_json_raw = _load_json_env(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        default=None,
    )
    pickup_goal_pose_raw = pickup_goal_pose_json_raw
    destination_goal_poses_raw = destination_goal_poses_json_raw
    return_to_dock_goal_pose_raw = return_to_dock_goal_pose_json_raw

    if pickup_goal_pose_raw is None:
        pickup_goal_pose_string = _load_raw_env("ROPI_DELIVERY_PICKUP_GOAL_POSE")
        if pickup_goal_pose_string:
            pickup_goal_pose_raw = parse_goal_pose_string(
                pickup_goal_pose_string,
                env_name="ROPI_DELIVERY_PICKUP_GOAL_POSE",
            )

    if destination_goal_poses_raw == {}:
        destination_goal_poses_string = _load_raw_env("ROPI_DELIVERY_DESTINATION_GOAL_POSES")
        if destination_goal_poses_string:
            destination_goal_poses_raw = parse_goal_pose_map_string(
                destination_goal_poses_string,
                env_name="ROPI_DELIVERY_DESTINATION_GOAL_POSES",
            )

    if return_to_dock_goal_pose_raw is None:
        return_to_dock_goal_pose_string = _load_raw_env("ROPI_RETURN_TO_DOCK_GOAL_POSE")
        if return_to_dock_goal_pose_string:
            return_to_dock_goal_pose_raw = parse_goal_pose_string(
                return_to_dock_goal_pose_string,
                env_name="ROPI_RETURN_TO_DOCK_GOAL_POSE",
            )

    if not isinstance(destination_goal_poses_raw, dict):
        raise RuntimeError(
            "ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON는 destination_id -> goal_pose map JSON object여야 합니다."
        )

    normalized_destination_goal_poses = {
        str(destination_id): normalize_goal_pose_spec(
            goal_pose,
            env_name=f"ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON[{destination_id}]",
        )
        for destination_id, goal_pose in destination_goal_poses_raw.items()
        if isinstance(goal_pose, dict)
    }

    return {
        "pickup_goal_pose": normalize_goal_pose_spec(
            pickup_goal_pose_raw,
            env_name="ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON",
        ),
        "destination_goal_poses": normalized_destination_goal_poses,
        "return_to_dock_goal_pose": normalize_goal_pose_spec(
            return_to_dock_goal_pose_raw,
            env_name="ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        ),
    }


__all__ = [
    "DeliveryRuntimeConfig",
    "_build_delivery_navigation_config_from_db_rows",
    "get_delivery_navigation_config",
    "get_delivery_runtime_config",
]
