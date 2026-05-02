def coerce_point2d(value):
    if not isinstance(value, dict):
        return None
    try:
        return {
            "x": float(value.get("x")),
            "y": float(value.get("y")),
        }
    except (TypeError, ValueError):
        return None


def coerce_pose2d(value, *, default_yaw=0.0):
    point = coerce_point2d(value)
    if point is None:
        return None
    try:
        yaw = float(value.get("yaw", default_yaw))
    except (TypeError, ValueError):
        return None
    return {
        **point,
        "yaw": yaw,
    }


def nearest_pose_index(poses, world_pose, *, threshold_world=0.08):
    target = coerce_point2d(world_pose)
    if target is None:
        return None

    best_index = None
    best_distance = float(threshold_world)
    for index, pose in enumerate(poses or []):
        point = coerce_point2d(pose)
        if point is None:
            continue
        distance = (
            (point["x"] - target["x"]) ** 2
            + (point["y"] - target["y"]) ** 2
        ) ** 0.5
        if distance <= best_distance:
            best_index = index
            best_distance = distance
    return best_index


def replace_index(rows, index, value):
    if not _valid_index(rows, index):
        return None
    next_rows = [dict(row) if isinstance(row, dict) else row for row in rows]
    next_rows[int(index)] = dict(value)
    return next_rows


def delete_index(rows, index):
    if not _valid_index(rows, index):
        return None
    next_rows = [dict(row) if isinstance(row, dict) else row for row in rows]
    del next_rows[int(index)]
    next_index = min(int(index), len(next_rows) - 1) if next_rows else None
    return next_rows, next_index


def move_index(rows, index, offset):
    if not _valid_index(rows, index):
        return None
    next_index = int(index) + int(offset)
    if not _valid_index(rows, next_index):
        return None

    next_rows = [dict(row) if isinstance(row, dict) else row for row in rows]
    next_rows[int(index)], next_rows[next_index] = (
        next_rows[next_index],
        next_rows[int(index)],
    )
    return next_rows, next_index


def _valid_index(rows, index):
    try:
        index = int(index)
    except (TypeError, ValueError):
        return False
    return 0 <= index < len(rows or [])


__all__ = [
    "coerce_point2d",
    "coerce_pose2d",
    "delete_index",
    "move_index",
    "nearest_pose_index",
    "replace_index",
]
