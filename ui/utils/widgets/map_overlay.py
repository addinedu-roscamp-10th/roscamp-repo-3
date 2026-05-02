from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPainterPath, QPen

from ui.utils.widgets.map_canvas import MapCanvasWidget, MapTransform


class PatrolMapOverlay(MapCanvasWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patrolMapOverlay")
        self.route_pixel_points = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.status_text = "순찰 맵 미수신"

    def render(self, task):
        task = task if isinstance(task, dict) else {}
        task_type = str(task.get("task_type") or "").strip().upper()

        if task_type and task_type != "PATROL":
            self._clear_overlay("순찰 맵 미수신")
            return

        if not task:
            self._clear_overlay("순찰 맵 미수신")
            return

        self._load_map(task.get("patrol_map") or {})
        self._sync_overlay_points(task)
        self.update()

    def _load_map(self, map_payload):
        map_payload = map_payload if isinstance(map_payload, dict) else {}
        self.load_map_from_paths(
            yaml_path=map_payload.get("yaml_path"),
            pgm_path=map_payload.get("pgm_path"),
        )

    def _sync_overlay_points(self, task):
        path = (
            task.get("patrol_path")
            if isinstance(task.get("patrol_path"), dict)
            else {}
        )
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

    def _clear_overlay(self, status_text):
        self.route_pixel_points = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.clear_map(status_text)

    def draw_overlay(self, painter, target):
        self._draw_route(painter, target)
        self._draw_robot(painter, target)
        self._draw_fall_alert(painter, target)

    def _draw_route(self, painter, target):
        points = [
            point
            for point in (
                self.to_view_point(pixel, target)
                for pixel in self.route_pixel_points
            )
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
            painter.setBrush(
                QColor(
                    "#FACC15"
                    if index == self.current_waypoint_index
                    else "#E0F2FE"
                )
            )
            painter.drawEllipse(point, radius, radius)

    def _draw_robot(self, painter, target):
        point = self.to_view_point(self.robot_pixel_point, target)
        if point is None:
            return
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.setBrush(QColor("#2563EB"))
        painter.drawEllipse(point, 7, 7)

    def _draw_fall_alert(self, painter, target):
        point = self.to_view_point(self.fall_alert_pixel_point, target)
        if point is None:
            return
        pen = QPen(QColor("#DC2626"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor("#FEE2E2"))
        painter.drawEllipse(point, 9, 9)
        painter.drawLine(
            QPointF(point.x() - 12, point.y()),
            QPointF(point.x() + 12, point.y()),
        )
        painter.drawLine(
            QPointF(point.x(), point.y() - 12),
            QPointF(point.x(), point.y() + 12),
        )

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["MapTransform", "PatrolMapOverlay"]
