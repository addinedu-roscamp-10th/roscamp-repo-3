from dataclasses import dataclass
from pathlib import Path

import yaml
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class MapTransform:
    resolution: float
    origin_x: float
    origin_y: float
    origin_yaw: float
    image_width: int
    image_height: int

    def world_to_pixel(self, pose):
        if not isinstance(pose, dict):
            return None
        try:
            x = float(pose.get("x"))
            y = float(pose.get("y"))
        except (TypeError, ValueError):
            return None
        if self.resolution <= 0:
            return None

        if abs(self.origin_yaw) > 1e-9:
            return None

        pixel_x = (x - self.origin_x) / self.resolution
        pixel_y = self.image_height - ((y - self.origin_y) / self.resolution)
        return (int(round(pixel_x)), int(round(pixel_y)))


def _resolve_path(path_text, *, relative_to=None):
    text = str(path_text or "").strip()
    if not text:
        return None

    path = Path(text).expanduser()
    if path.is_absolute():
        return path

    if relative_to is not None:
        candidate = relative_to / path
        if candidate.exists():
            return candidate

    return PROJECT_ROOT / path


def _load_yaml(path):
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return data if isinstance(data, dict) else {}


class PatrolMapOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patrolMapOverlay")
        self.setMinimumHeight(160)
        self.map_loaded = False
        self.map_image_size = None
        self.route_pixel_points = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.status_text = "순찰 맵 미수신"
        self._map_image = QImage()
        self._map_transform = None
        self._map_cache_key = None

    def render(self, task):
        task = task if isinstance(task, dict) else {}
        task_type = str(task.get("task_type") or "").strip().upper()

        if task_type and task_type != "PATROL":
            self._clear("순찰 맵 미수신")
            return

        if not task:
            self._clear("순찰 맵 미수신")
            return

        self._load_map(task.get("patrol_map") or {})
        self._sync_overlay_points(task)
        self.update()

    def world_to_pixel(self, pose):
        if self._map_transform is None:
            return None
        return self._map_transform.world_to_pixel(pose)

    def _load_map(self, map_payload):
        map_payload = map_payload if isinstance(map_payload, dict) else {}
        yaml_path = _resolve_path(map_payload.get("yaml_path"))
        pgm_path = _resolve_path(map_payload.get("pgm_path"))
        cache_key = (
            str(yaml_path) if yaml_path else "",
            str(pgm_path) if pgm_path else "",
        )

        if cache_key == self._map_cache_key:
            return

        self._map_cache_key = cache_key
        self.map_loaded = False
        self.map_image_size = None
        self._map_image = QImage()
        self._map_transform = None

        if yaml_path is None or not yaml_path.exists():
            self.status_text = "맵 YAML 파일을 찾을 수 없습니다."
            return

        try:
            yaml_data = _load_yaml(yaml_path)
            if pgm_path is None:
                pgm_path = _resolve_path(
                    yaml_data.get("image"),
                    relative_to=yaml_path.parent,
                )
            image = QImage(str(pgm_path)) if pgm_path is not None else QImage()
            if image.isNull():
                self.status_text = "맵 PGM 파일을 읽을 수 없습니다."
                return

            origin = yaml_data.get("origin") or [0.0, 0.0, 0.0]
            self._map_image = image
            self._map_transform = MapTransform(
                resolution=float(yaml_data.get("resolution")),
                origin_x=float(origin[0]),
                origin_y=float(origin[1]),
                origin_yaw=float(origin[2]) if len(origin) > 2 else 0.0,
                image_width=image.width(),
                image_height=image.height(),
            )
            self.map_loaded = True
            self.map_image_size = (image.width(), image.height())
            self.status_text = ""
        except Exception as exc:
            self.status_text = f"맵 로드 실패: {exc}"

    def _sync_overlay_points(self, task):
        path = task.get("patrol_path") if isinstance(task.get("patrol_path"), dict) else {}
        poses = path.get("poses") if isinstance(path, dict) else []
        if not isinstance(poses, list):
            poses = []

        self.route_pixel_points = [
            pixel
            for pixel in (self.world_to_pixel(pose) for pose in poses)
            if pixel is not None
        ]
        self.current_waypoint_index = self._optional_int(
            path.get("current_waypoint_index") if isinstance(path, dict) else None
        )

        robot_pose = task.get("pose")
        if not isinstance(robot_pose, dict):
            latest_robot = task.get("latest_robot")
            if isinstance(latest_robot, dict):
                robot_pose = latest_robot.get("pose")
        self.robot_pixel_point = self.world_to_pixel(robot_pose)

        alert = task.get("fall_alert") if isinstance(task.get("fall_alert"), dict) else {}
        self.fall_alert_pixel_point = self.world_to_pixel(
            alert.get("alert_pose") or alert.get("pose")
        )

        if not self.map_loaded:
            self.route_pixel_points = []
            self.robot_pixel_point = None
            self.fall_alert_pixel_point = None

    def _clear(self, status_text):
        self.map_loaded = False
        self.map_image_size = None
        self.route_pixel_points = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.status_text = status_text
        self._map_image = QImage()
        self._map_transform = None
        self._map_cache_key = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), QColor("#0F172A"))

            if not self.map_loaded or self._map_image.isNull():
                painter.setPen(QColor("#94A3B8"))
                painter.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    self.status_text or "순찰 맵 미수신",
                )
                return

            target = self._image_target_rect()
            painter.drawImage(target, self._map_image)
            self._draw_route(painter, target)
            self._draw_robot(painter, target)
            self._draw_fall_alert(painter, target)
        finally:
            painter.end()

    def _image_target_rect(self):
        margin = 10.0
        available = self.rect().adjusted(
            int(margin),
            int(margin),
            -int(margin),
            -int(margin),
        )
        if available.width() <= 0 or available.height() <= 0:
            return QRectF()

        image_ratio = self._map_image.width() / max(1, self._map_image.height())
        available_ratio = available.width() / max(1, available.height())
        if available_ratio > image_ratio:
            height = available.height()
            width = height * image_ratio
        else:
            width = available.width()
            height = width / image_ratio

        left = available.left() + (available.width() - width) / 2
        top = available.top() + (available.height() - height) / 2
        return QRectF(left, top, width, height)

    def _to_view_point(self, pixel_point, target):
        if pixel_point is None or self.map_image_size is None:
            return None
        width, height = self.map_image_size
        x, y = pixel_point
        return QPointF(
            target.left() + (float(x) / max(1, width)) * target.width(),
            target.top() + (float(y) / max(1, height)) * target.height(),
        )

    def _draw_route(self, painter, target):
        points = [
            point
            for point in (self._to_view_point(pixel, target) for pixel in self.route_pixel_points)
            if point is not None
        ]
        if not points:
            return

        if len(points) >= 2:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            pen = QPen(QColor("#38BDF8"))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawPath(path)

        for index, point in enumerate(points):
            radius = 6 if index == self.current_waypoint_index else 4
            painter.setPen(QPen(QColor("#0F172A"), 2))
            painter.setBrush(QColor("#FACC15" if index == self.current_waypoint_index else "#E0F2FE"))
            painter.drawEllipse(point, radius, radius)

    def _draw_robot(self, painter, target):
        point = self._to_view_point(self.robot_pixel_point, target)
        if point is None:
            return
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.setBrush(QColor("#2563EB"))
        painter.drawEllipse(point, 7, 7)

    def _draw_fall_alert(self, painter, target):
        point = self._to_view_point(self.fall_alert_pixel_point, target)
        if point is None:
            return
        pen = QPen(QColor("#DC2626"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor("#FEE2E2"))
        painter.drawEllipse(point, 9, 9)
        painter.drawLine(QPointF(point.x() - 12, point.y()), QPointF(point.x() + 12, point.y()))
        painter.drawLine(QPointF(point.x(), point.y() - 12), QPointF(point.x(), point.y() + 12))

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["MapTransform", "PatrolMapOverlay"]
