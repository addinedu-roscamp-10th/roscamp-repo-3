from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen


def drive_route_label(active_drive_task) -> str:
    active_drive_task = (
        active_drive_task if isinstance(active_drive_task, dict) else {}
    )
    return (
        str(active_drive_task.get("route_name") or "").strip()
        or str(active_drive_task.get("route_id") or "").strip()
        or "-"
    )


def drive_target_waypoint(active_drive_task):
    active_drive_task = (
        active_drive_task if isinstance(active_drive_task, dict) else {}
    )
    route_path = active_drive_task.get("route_path")
    route_path = route_path if isinstance(route_path, dict) else {}
    poses = route_path.get("poses") if isinstance(route_path.get("poses"), list) else []

    target_index = _target_index_from_current(active_drive_task, len(poses))
    if target_index is not None and 1 <= target_index <= len(poses):
        pose = poses[target_index - 1]
        if isinstance(pose, dict):
            return dict(pose, target_waypoint_index=target_index)

    target = active_drive_task.get("target_waypoint")
    if isinstance(target, dict):
        return dict(target)
    return None


def drive_target_waypoint_text(active_drive_task) -> str:
    target = drive_target_waypoint(active_drive_task)
    if not isinstance(target, dict):
        return "-"
    waypoint_id = str(target.get("waypoint_id") or "").strip()
    if waypoint_id:
        return waypoint_id
    sequence_no = target.get("sequence_no") or target.get("target_waypoint_index")
    return f"#{sequence_no}" if sequence_no not in (None, "") else "-"


def build_drive_route_markers(canvas, robots, *, selected_map_id):
    selected_map_id = str(selected_map_id or "").strip()
    if not selected_map_id or not getattr(canvas, "map_loaded", False):
        return []

    markers = []
    for robot in robots or []:
        if not isinstance(robot, dict):
            continue
        active_drive = robot.get("active_drive_task")
        if not isinstance(active_drive, dict):
            continue
        route_path = (
            active_drive.get("route_path")
            if isinstance(active_drive.get("route_path"), dict)
            else {}
        )
        map_id = (
            str(route_path.get("map_id") or active_drive.get("map_id") or "").strip()
            or _robot_pose_map_id(robot)
        )
        if map_id != selected_map_id:
            continue

        poses = route_path.get("poses") if isinstance(route_path.get("poses"), list) else []
        route_pixel_points = []
        route_pose_indexes = []
        for index, pose in enumerate(poses, start=1):
            if not isinstance(pose, dict):
                continue
            pixel = canvas.world_to_pixel(pose)
            if pixel is None:
                continue
            route_pixel_points.append(pixel)
            route_pose_indexes.append(index)

        if not route_pixel_points:
            continue

        target = drive_target_waypoint(active_drive)
        target_index = _target_index_from_current(active_drive, len(poses))
        target_route_index = (
            route_pose_indexes.index(target_index)
            if target_index in route_pose_indexes
            else None
        )
        markers.append(
            {
                "robot_id": str(
                    robot.get("robot_id") or robot.get("robot_name") or ""
                ).strip(),
                "route_id": str(active_drive.get("route_id") or "").strip(),
                "route_name": drive_route_label(active_drive),
                "route_pixel_points": route_pixel_points,
                "target_route_index": target_route_index,
                "target_waypoint_id": (
                    str((target or {}).get("waypoint_id") or "").strip() or None
                ),
            }
        )
    return markers


def draw_drive_route_markers(canvas, painter, target, markers):
    for marker in markers or []:
        points = [
            point
            for point in (
                canvas.to_view_point(pixel, target)
                for pixel in marker.get("route_pixel_points") or []
            )
            if point is not None
        ]
        if not points:
            continue

        if len(points) >= 2:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.save()
            pen = QPen(QColor("#0EA5E9"))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()

        target_route_index = marker.get("target_route_index")
        for index, point in enumerate(points):
            is_target = index == target_route_index
            painter.setPen(QPen(QColor("#0F172A"), 2))
            painter.setBrush(QColor("#FACC15" if is_target else "#DBEAFE"))
            painter.drawEllipse(point, 7 if is_target else 4, 7 if is_target else 4)

        if target_route_index is None or not (0 <= target_route_index < len(points)):
            continue
        label = _target_label(marker)
        if not label:
            continue
        painter.setPen(QPen(QColor("#111827"), 1))
        painter.drawText(points[target_route_index] + QPointF(9, -9), label)


def _target_label(marker):
    robot_id = str(marker.get("robot_id") or "").strip()
    waypoint_id = str(marker.get("target_waypoint_id") or "").strip()
    if not waypoint_id:
        return robot_id
    return f"{robot_id} -> {waypoint_id}" if robot_id else waypoint_id


def _target_index_from_current(active_drive_task, pose_count: int):
    current_index = _optional_int(
        (active_drive_task or {}).get("current_waypoint_index")
    )
    if current_index is None:
        explicit = _optional_int((active_drive_task or {}).get("target_waypoint_index"))
        if explicit is not None:
            return explicit
        current_index = 0
    target_index = current_index + 1
    if target_index < 1 or target_index > pose_count:
        return None
    return target_index


def _robot_pose_map_id(robot):
    pose = robot.get("current_pose") if isinstance(robot, dict) else None
    if not isinstance(pose, dict):
        return ""
    return str(pose.get("map_id") or "").strip()


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "build_drive_route_markers",
    "draw_drive_route_markers",
    "drive_route_label",
    "drive_target_waypoint",
    "drive_target_waypoint_text",
]
