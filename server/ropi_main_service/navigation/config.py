import json
import os
from pathlib import Path

from dotenv import load_dotenv
from server.ropi_main_service.navigation.pose_spec import (
    normalize_goal_pose_spec,
    parse_goal_pose_map_string,
    parse_goal_pose_string,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")


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


def get_delivery_navigation_config() -> dict:
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


__all__ = ["get_delivery_navigation_config"]
