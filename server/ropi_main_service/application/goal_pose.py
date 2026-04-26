import math
from copy import deepcopy


DEFAULT_FRAME_ID = "map"


def normalize_goal_pose_spec(spec: dict | None, *, env_name: str) -> dict | None:
    if spec is None:
        return None

    if not isinstance(spec, dict):
        raise RuntimeError(f"{env_name}는 goal_pose JSON object여야 합니다.")

    if _looks_like_pose_stamped(spec):
        return _normalize_pose_stamped(spec)

    if _looks_like_simple_2d_pose(spec):
        return _build_pose_stamped_from_simple_2d_pose(spec)

    raise RuntimeError(
        f"{env_name}는 PoseStamped object 또는 {{x, y, yaw}} 형식이어야 합니다."
    )


def _looks_like_pose_stamped(spec: dict) -> bool:
    return "header" in spec or "pose" in spec


def _looks_like_simple_2d_pose(spec: dict) -> bool:
    has_yaw = "yaw" in spec or "yaw_deg" in spec
    return "x" in spec and "y" in spec and has_yaw


def _normalize_pose_stamped(spec: dict) -> dict:
    normalized = deepcopy(spec)
    header = normalized.setdefault("header", {})
    header.setdefault("stamp", {"sec": 0, "nanosec": 0})
    if not str(header.get("frame_id", "")).strip():
        header["frame_id"] = DEFAULT_FRAME_ID
    return normalized


def _build_pose_stamped_from_simple_2d_pose(spec: dict) -> dict:
    yaw = _extract_yaw_radians(spec)
    return {
        "header": {
            "stamp": {"sec": 0, "nanosec": 0},
            "frame_id": str(spec.get("frame_id") or DEFAULT_FRAME_ID).strip() or DEFAULT_FRAME_ID,
        },
        "pose": {
            "position": {
                "x": float(spec["x"]),
                "y": float(spec["y"]),
                "z": float(spec.get("z", 0.0)),
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": math.sin(yaw / 2.0),
                "w": math.cos(yaw / 2.0),
            },
        },
    }


def _extract_yaw_radians(spec: dict) -> float:
    if "yaw" in spec:
        return float(spec["yaw"])

    if "yaw_deg" in spec:
        return math.radians(float(spec["yaw_deg"]))

    raise RuntimeError("2D goal pose에는 yaw 또는 yaw_deg가 필요합니다.")

def parse_goal_pose_string(raw: str, *, env_name: str) -> dict:
    parts = [part.strip() for part in str(raw or "").split(",") if part.strip()]
    if not parts:
        raise RuntimeError(f"{env_name}가 비어 있습니다.")

    if any("=" in part for part in parts):
        return _parse_key_value_goal_pose_string(parts, env_name=env_name)

    if len(parts) not in {3, 4, 5}:
        raise RuntimeError(
            f"{env_name}는 'x,y,yaw' 또는 'x,y,yaw,frame_id' 또는 'x,y,yaw,z,frame_id' "
            "또는 'x=...,y=...,yaw_deg=...' 형식이어야 합니다."
        )

    x = float(parts[0])
    y = float(parts[1])
    yaw = float(parts[2])

    z = 0.0
    frame_id = DEFAULT_FRAME_ID

    if len(parts) == 4:
        frame_id = parts[3] or DEFAULT_FRAME_ID
    elif len(parts) == 5:
        z = float(parts[3])
        frame_id = parts[4] or DEFAULT_FRAME_ID

    return _build_pose_stamped_from_simple_2d_pose(
        {
            "x": x,
            "y": y,
            "yaw": yaw,
            "z": z,
            "frame_id": frame_id,
        }
    )


def _parse_key_value_goal_pose_string(parts: list[str], *, env_name: str) -> dict:
    spec = {}

    for part in parts:
        if "=" not in part:
            raise RuntimeError(
                f"{env_name}는 'x=...,y=...,yaw_deg=...' 형식일 때 모든 항목이 key=value여야 합니다."
            )

        key, value = part.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key:
            raise RuntimeError(f"{env_name}의 key가 비어 있습니다.")
        if not normalized_value:
            raise RuntimeError(f"{env_name}[{normalized_key}] 값이 비어 있습니다.")
        spec[normalized_key] = normalized_value

    try:
        normalized_spec = {
            "x": float(spec["x"]),
            "y": float(spec["y"]),
            "z": float(spec.get("z", 0.0)),
            "frame_id": str(spec.get("frame_id") or DEFAULT_FRAME_ID).strip() or DEFAULT_FRAME_ID,
        }
    except KeyError as exc:
        raise RuntimeError(
            f"{env_name}는 x, y와 yaw 또는 yaw_deg를 포함해야 합니다."
        ) from exc

    if "yaw" in spec:
        normalized_spec["yaw"] = float(spec["yaw"])
    elif "yaw_deg" in spec:
        normalized_spec["yaw_deg"] = float(spec["yaw_deg"])
    else:
        raise RuntimeError(
            f"{env_name}는 x, y와 yaw 또는 yaw_deg를 포함해야 합니다."
        )

    return _build_pose_stamped_from_simple_2d_pose(normalized_spec)


def parse_goal_pose_map_string(raw: str, *, env_name: str) -> dict:
    mapping = {}
    entries = [
        entry.strip()
        for entry in str(raw or "").replace("\n", ";").split(";")
        if entry.strip()
    ]

    for entry in entries:
        if "=" not in entry:
            raise RuntimeError(
                f"{env_name}의 각 항목은 'destination_id=x,y,yaw' 또는 "
                "'destination_id=x=...,y=...,yaw_deg=...' 형식이어야 합니다."
            )

        destination_id, pose_raw = entry.split("=", 1)
        normalized_destination_id = destination_id.strip()
        if not normalized_destination_id:
            raise RuntimeError(f"{env_name}의 destination_id가 비어 있습니다.")

        mapping[normalized_destination_id] = parse_goal_pose_string(
            pose_raw,
            env_name=f"{env_name}[{normalized_destination_id}]",
        )

    return mapping


__all__ = [
    "normalize_goal_pose_spec",
    "parse_goal_pose_map_string",
    "parse_goal_pose_string",
]
