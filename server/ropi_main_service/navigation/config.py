import json
import os
from pathlib import Path

from dotenv import load_dotenv


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


def get_delivery_navigation_config() -> dict:
    pickup_goal_pose = _load_json_env(
        "ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON",
        default=None,
    )
    destination_goal_poses = _load_json_env(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON",
        default={},
    )
    return_to_dock_goal_pose = _load_json_env(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        default=None,
    )

    if pickup_goal_pose is not None and not isinstance(pickup_goal_pose, dict):
        raise RuntimeError("ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON는 goal_pose JSON object여야 합니다.")

    if not isinstance(destination_goal_poses, dict):
        raise RuntimeError(
            "ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON는 destination_id -> goal_pose map JSON object여야 합니다."
        )

    if return_to_dock_goal_pose is not None and not isinstance(return_to_dock_goal_pose, dict):
        raise RuntimeError("ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON는 goal_pose JSON object여야 합니다.")

    normalized_destination_goal_poses = {
        str(destination_id): goal_pose
        for destination_id, goal_pose in destination_goal_poses.items()
        if isinstance(goal_pose, dict)
    }

    return {
        "pickup_goal_pose": pickup_goal_pose,
        "destination_goal_poses": normalized_destination_goal_poses,
        "return_to_dock_goal_pose": return_to_dock_goal_pose,
    }


__all__ = ["get_delivery_navigation_config"]
