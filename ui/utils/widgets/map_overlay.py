import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen

from ui.utils.widgets.map_canvas import MapCanvasWidget, MapTransform


class OperationalMapOverlay(MapCanvasWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patrolMapOverlay")
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self._heading_drag_active = False
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
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None

        path = (
            task.get("patrol_path") if isinstance(task.get("patrol_path"), dict) else {}
        )
        poses = path.get("poses") if isinstance(path, dict) else []
        if not isinstance(poses, list):
            poses = []

        self.route_pixel_points = []
        self.route_heading_yaws = []
        for pose in poses:
            pixel = self.world_to_pixel(pose)
            if pixel is None:
                continue
            self.route_pixel_points.append(pixel)
            self.route_heading_yaws.append(self._pose_yaw(pose))
        self.current_waypoint_index = self._optional_int(
            path.get("current_waypoint_index") if isinstance(path, dict) else None
        )

        robot_pose = task.get("pose")
        if not isinstance(robot_pose, dict):
            latest_robot = task.get("latest_robot")
            if isinstance(latest_robot, dict):
                robot_pose = latest_robot.get("pose")
        self.robot_pixel_point = self.world_to_pixel(robot_pose)

        alert = (
            task.get("fall_alert") if isinstance(task.get("fall_alert"), dict) else {}
        )
        self.fall_alert_pixel_point = self.world_to_pixel(
            alert.get("alert_pose") or alert.get("pose")
        )

        if not self.map_loaded:
            self.route_pixel_points = []
            self.route_heading_yaws = []
            self.robot_pixel_point = None
            self.fall_alert_pixel_point = None

    def _clear_overlay(self, status_text):
        self._heading_drag_active = False
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.clear_map(status_text)

    def show_zone_boundary_editor(self, *, vertex_pixel_points, selected_index=None):
        self.zone_boundary_pixel_points = list(vertex_pixel_points or [])
        self.selected_zone_boundary_vertex_index = selected_index
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def show_goal_pose_editor(
        self,
        *,
        goal_pose_pixel_points,
        goal_pose_yaws=None,
        selected_pixel_point=None,
        selected_yaw=None,
    ):
        self.goal_pose_pixel_points = list(goal_pose_pixel_points or [])
        self.goal_pose_heading_yaws = self._normalized_yaws(
            goal_pose_yaws,
            len(self.goal_pose_pixel_points),
        )
        self.selected_goal_pose_pixel_point = selected_pixel_point
        self.selected_goal_pose_heading_yaw = self._optional_float(selected_yaw)
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def show_patrol_path_editor(
        self,
        *,
        route_pixel_points,
        route_yaws=None,
        selected_waypoint_index=None,
    ):
        self.route_pixel_points = list(route_pixel_points or [])
        self.route_heading_yaws = self._normalized_yaws(
            route_yaws,
            len(self.route_pixel_points),
        )
        self.current_waypoint_index = selected_waypoint_index
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def show_fms_waypoint_editor(
        self,
        *,
        fms_waypoint_pixel_points,
        fms_waypoint_labels=None,
        fms_waypoint_yaws=None,
        selected_pixel_point=None,
        selected_yaw=None,
    ):
        self.fms_waypoint_pixel_points = list(fms_waypoint_pixel_points or [])
        self.fms_waypoint_labels = self._normalized_labels(
            fms_waypoint_labels,
            len(self.fms_waypoint_pixel_points),
        )
        self.fms_waypoint_heading_yaws = self._normalized_yaws(
            fms_waypoint_yaws,
            len(self.fms_waypoint_pixel_points),
        )
        self.selected_fms_waypoint_pixel_point = selected_pixel_point
        self.selected_fms_waypoint_heading_yaw = self._optional_float(selected_yaw)
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def show_fms_edge_editor(
        self,
        *,
        fms_waypoint_pixel_points,
        fms_waypoint_labels=None,
        fms_edge_pixel_pairs=None,
        selected_edge_pixel_pair=None,
    ):
        self.fms_waypoint_pixel_points = list(fms_waypoint_pixel_points or [])
        self.fms_waypoint_labels = self._normalized_labels(
            fms_waypoint_labels,
            len(self.fms_waypoint_pixel_points),
        )
        self.fms_waypoint_heading_yaws = self._normalized_yaws(
            [],
            len(self.fms_waypoint_pixel_points),
        )
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = [
            tuple(pair)
            for pair in fms_edge_pixel_pairs or []
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        ]
        self.selected_fms_edge_pixel_pair = selected_edge_pixel_pair
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def show_fms_route_editor(
        self,
        *,
        route_pixel_points,
        route_labels=None,
        selected_route_index=None,
    ):
        self.fms_route_pixel_points = list(route_pixel_points or [])
        self.fms_route_labels = self._normalized_labels(
            route_labels,
            len(self.fms_route_pixel_points),
        )
        self.selected_fms_route_index = selected_route_index
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.update()

    def clear_configuration_overlay(self):
        self._heading_drag_active = False
        self.route_pixel_points = []
        self.route_heading_yaws = []
        self.current_waypoint_index = None
        self.robot_pixel_point = None
        self.fall_alert_pixel_point = None
        self.zone_boundary_pixel_points = []
        self.selected_zone_boundary_vertex_index = None
        self.goal_pose_pixel_points = []
        self.goal_pose_heading_yaws = []
        self.selected_goal_pose_pixel_point = None
        self.selected_goal_pose_heading_yaw = None
        self.fms_waypoint_pixel_points = []
        self.fms_waypoint_labels = []
        self.fms_waypoint_heading_yaws = []
        self.selected_fms_waypoint_pixel_point = None
        self.selected_fms_waypoint_heading_yaw = None
        self.fms_edge_pixel_pairs = []
        self.selected_fms_edge_pixel_pair = None
        self.fms_route_pixel_points = []
        self.fms_route_labels = []
        self.selected_fms_route_index = None
        self.update()

    def draw_overlay(self, painter, target):
        self._draw_zone_boundary(painter, target)
        self._draw_goal_poses(painter, target)
        self._draw_fms_edges(painter, target)
        self._draw_fms_waypoints(painter, target)
        self._draw_fms_route(painter, target)
        self._draw_route(painter, target)
        self._draw_robot(painter, target)
        self._draw_fall_alert(painter, target)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_heading_handle_hit(
            event.position()
        ):
            self._heading_drag_active = True
            event.accept()
            return

        self._heading_drag_active = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._heading_drag_active and event.buttons() & Qt.MouseButton.LeftButton:
            world_pose = self.view_to_world(event.position())
            payload = self.heading_drag_payload_for_world_target(world_pose)
            if payload is not None:
                self.map_heading_dragged.emit(payload)
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._heading_drag_active:
            self._heading_drag_active = False
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def heading_drag_payload_for_world_target(self, world_pose):
        context = self._selected_heading_context()
        if context is None or not isinstance(world_pose, dict):
            return None

        origin = self.pixel_to_world(context["pixel"])
        if not isinstance(origin, dict):
            return None

        try:
            origin_x = float(origin.get("x"))
            origin_y = float(origin.get("y"))
            target_x = float(world_pose.get("x"))
            target_y = float(world_pose.get("y"))
        except (TypeError, ValueError):
            return None

        delta_x = target_x - origin_x
        delta_y = target_y - origin_y
        if abs(delta_x) < 1e-9 and abs(delta_y) < 1e-9:
            return None
        return {"yaw": math.atan2(delta_y, delta_x)}

    def _is_heading_handle_hit(self, view_point):
        handle = self._selected_heading_handle_view_point()
        if handle is None:
            return False
        delta_x = float(view_point.x()) - handle.x()
        delta_y = float(view_point.y()) - handle.y()
        return math.hypot(delta_x, delta_y) <= 12.0

    def _selected_heading_handle_view_point(self):
        context = self._selected_heading_context()
        if context is None:
            return None
        target = self.image_target_rect()
        if target.isNull():
            return None
        origin = self.to_view_point(context["pixel"], target)
        if origin is None:
            return None
        yaw = self._optional_float(context.get("yaw"))
        return self._heading_endpoint(
            origin,
            yaw if yaw is not None else 0.0,
            context["length"],
        )

    def _selected_heading_context(self):
        if self.selected_goal_pose_pixel_point is not None:
            return {
                "pixel": self.selected_goal_pose_pixel_point,
                "yaw": self.selected_goal_pose_heading_yaw,
                "length": 18.0,
            }
        if self.selected_fms_waypoint_pixel_point is not None:
            return {
                "pixel": self.selected_fms_waypoint_pixel_point,
                "yaw": self.selected_fms_waypoint_heading_yaw,
                "length": 18.0,
            }
        index = self.current_waypoint_index
        if index is not None and 0 <= index < len(self.route_pixel_points):
            yaw = (
                self.route_heading_yaws[index]
                if index < len(self.route_heading_yaws)
                else None
            )
            return {
                "pixel": self.route_pixel_points[index],
                "yaw": yaw,
                "length": 15.0,
            }
        return None

    def _draw_zone_boundary(self, painter, target):
        points = [
            point
            for point in (
                self.to_view_point(pixel, target)
                for pixel in self.zone_boundary_pixel_points
            )
            if point is not None
        ]
        if not points:
            return

        if len(points) >= 3:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            path.closeSubpath()
            fill_color = QColor("#F97316")
            fill_color.setAlpha(55)
            painter.setBrush(fill_color)
            painter.setPen(QPen(QColor("#EA580C"), 2))
            painter.drawPath(path)
        elif len(points) == 2:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#EA580C"), 2))
            painter.drawLine(points[0], points[1])

        for index, point in enumerate(points):
            selected = index == self.selected_zone_boundary_vertex_index
            painter.setPen(QPen(QColor("#7C2D12"), 2))
            painter.setBrush(QColor("#FDBA74" if selected else "#FFEDD5"))
            painter.drawEllipse(point, 6 if selected else 4, 6 if selected else 4)

    def _draw_goal_poses(self, painter, target):
        for point, yaw in zip(
            (
                self.to_view_point(pixel, target)
                for pixel in self.goal_pose_pixel_points
            ),
            self.goal_pose_heading_yaws,
        ):
            if point is None:
                continue
            painter.setPen(QPen(QColor("#0F172A"), 2))
            painter.setBrush(QColor("#22C55E"))
            painter.drawEllipse(point, 5, 5)
            self._draw_heading_arrow(
                painter,
                point,
                yaw,
                QColor("#15803D"),
                length=14.0,
                width=2,
            )

        selected = self.to_view_point(self.selected_goal_pose_pixel_point, target)
        if selected is None:
            return
        painter.setPen(QPen(QColor("#052E16"), 2))
        painter.setBrush(QColor("#86EFAC"))
        painter.drawEllipse(selected, 7, 7)
        self._draw_heading_arrow(
            painter,
            selected,
            self.selected_goal_pose_heading_yaw,
            QColor("#052E16"),
            length=18.0,
            width=3,
        )

    def _draw_route(self, painter, target):
        points = []
        yaws = []
        route_yaws = self._normalized_yaws(
            self.route_heading_yaws,
            len(self.route_pixel_points),
        )
        for pixel, yaw in zip(self.route_pixel_points, route_yaws):
            point = self.to_view_point(pixel, target)
            if point is None:
                continue
            points.append(point)
            yaws.append(yaw)
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
                QColor("#FACC15" if index == self.current_waypoint_index else "#E0F2FE")
            )
            painter.drawEllipse(point, radius, radius)
            self._draw_heading_arrow(
                painter,
                point,
                yaws[index],
                QColor(
                    "#A16207" if index == self.current_waypoint_index else "#0369A1"
                ),
                length=15.0 if index == self.current_waypoint_index else 11.0,
                width=2,
            )

    def _draw_fms_edges(self, painter, target):
        for pair in self.fms_edge_pixel_pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            start = self.to_view_point(pair[0], target)
            end = self.to_view_point(pair[1], target)
            if start is None or end is None:
                continue
            selected = pair == self.selected_fms_edge_pixel_pair
            pen = QPen(QColor("#4F46E5" if selected else "#64748B"))
            pen.setWidth(4 if selected else 2)
            painter.setPen(pen)
            painter.drawLine(start, end)

    def _draw_fms_waypoints(self, painter, target):
        for pixel, label, yaw in zip(
            self.fms_waypoint_pixel_points,
            self.fms_waypoint_labels,
            self.fms_waypoint_heading_yaws,
        ):
            point = self.to_view_point(pixel, target)
            if point is None:
                continue
            painter.setPen(QPen(QColor("#312E81"), 2))
            painter.setBrush(QColor("#A5B4FC"))
            painter.drawEllipse(point, 5, 5)
            self._draw_heading_arrow(
                painter,
                point,
                yaw,
                QColor("#4338CA"),
                length=14.0,
                width=2,
            )
            if label:
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.drawText(point + QPointF(8, -8), str(label))

        selected = self.to_view_point(self.selected_fms_waypoint_pixel_point, target)
        if selected is None:
            return
        painter.setPen(QPen(QColor("#1E1B4B"), 2))
        painter.setBrush(QColor("#C7D2FE"))
        painter.drawEllipse(selected, 7, 7)
        self._draw_heading_arrow(
            painter,
            selected,
            self.selected_fms_waypoint_heading_yaw,
            QColor("#1E1B4B"),
            length=18.0,
            width=3,
        )

    def _draw_fms_route(self, painter, target):
        points = [
            point
            for point in (
                self.to_view_point(pixel, target)
                for pixel in self.fms_route_pixel_points
            )
            if point is not None
        ]
        if not points:
            return

        if len(points) >= 2:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            pen = QPen(QColor("#14B8A6"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawPath(path)

        labels = self._normalized_labels(self.fms_route_labels, len(points))
        for index, point in enumerate(points):
            selected = index == self.selected_fms_route_index
            painter.setPen(QPen(QColor("#134E4A"), 2))
            painter.setBrush(QColor("#5EEAD4" if selected else "#CCFBF1"))
            painter.drawEllipse(point, 7 if selected else 5, 7 if selected else 5)
            if labels[index]:
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.drawText(point + QPointF(8, -8), labels[index])

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

    @classmethod
    def _normalized_yaws(cls, values, length):
        yaws = [cls._optional_float(value) for value in values or []]
        if len(yaws) < length:
            yaws.extend([None] * (length - len(yaws)))
        return yaws[:length]

    @staticmethod
    def _normalized_labels(values, length):
        labels = [str(value or "") for value in values or []]
        if len(labels) < length:
            labels.extend([""] * (length - len(labels)))
        return labels[:length]

    @classmethod
    def _pose_yaw(cls, pose):
        if not isinstance(pose, dict):
            return None
        return cls._optional_float(pose.get("yaw", pose.get("pose_yaw")))

    @staticmethod
    def _optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _draw_heading_arrow(cls, painter, point, yaw, color, *, length, width):
        yaw = cls._optional_float(yaw)
        if point is None or yaw is None:
            return

        end = cls._heading_endpoint(point, yaw, length)
        head_left = cls._heading_endpoint(end, yaw + math.pi - 0.55, 5.0)
        head_right = cls._heading_endpoint(end, yaw + math.pi + 0.55, 5.0)

        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(point, end)
        painter.drawLine(end, head_left)
        painter.drawLine(end, head_right)

    @staticmethod
    def _heading_endpoint(point, yaw, length):
        return QPointF(
            point.x() + (math.cos(yaw) * length),
            point.y() - (math.sin(yaw) * length),
        )


PatrolMapOverlay = OperationalMapOverlay


__all__ = ["MapTransform", "OperationalMapOverlay", "PatrolMapOverlay"]
