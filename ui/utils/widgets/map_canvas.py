from dataclasses import dataclass
from pathlib import Path

import yaml
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
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
        pixel = self.world_to_pixel_float(pose)
        if pixel is None:
            return None
        pixel_x, pixel_y = pixel
        return (int(round(pixel_x)), int(round(pixel_y)))

    def world_to_pixel_float(self, pose):
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
        return (pixel_x, pixel_y)

    def pixel_to_world(self, pixel_point):
        if pixel_point is None or self.resolution <= 0:
            return None
        if abs(self.origin_yaw) > 1e-9:
            return None

        try:
            pixel_x, pixel_y = pixel_point
            pixel_x = float(pixel_x)
            pixel_y = float(pixel_y)
        except (TypeError, ValueError):
            return None

        return {
            "x": round(self.origin_x + (pixel_x * self.resolution), 6),
            "y": round(
                self.origin_y + ((self.image_height - pixel_y) * self.resolution),
                6,
            ),
        }

    def contains_world_pose(self, pose):
        pixel = self.world_to_pixel_float(pose)
        if pixel is None:
            return False
        x, y = pixel
        return 0 <= x < self.image_width and 0 <= y < self.image_height


def resolve_map_path(path_text, *, relative_to=None):
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


def load_map_yaml(path):
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return data if isinstance(data, dict) else {}


def parse_map_yaml_text(yaml_text):
    data = yaml.safe_load(str(yaml_text or "")) or {}
    return data if isinstance(data, dict) else {}


class MapCanvasWidget(QFrame):
    map_clicked = pyqtSignal(object)
    map_dragged = pyqtSignal(object)
    map_heading_dragged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mapCanvasWidget")
        self.setMinimumHeight(160)
        self.map_loaded = False
        self.map_image_size = None
        self.status_text = "맵 미수신"
        self._map_image = QImage()
        self._map_transform = None
        self._map_cache_key = None

    def load_map_from_paths(self, *, yaml_path, pgm_path=None, cache_key=None):
        resolved_yaml_path = resolve_map_path(yaml_path)
        resolved_pgm_path = resolve_map_path(pgm_path)
        next_cache_key = cache_key or (
            "paths",
            str(resolved_yaml_path) if resolved_yaml_path else "",
            str(resolved_pgm_path) if resolved_pgm_path else "",
        )

        if next_cache_key == self._map_cache_key:
            return

        self._reset_map_state(next_cache_key)

        if resolved_yaml_path is None or not resolved_yaml_path.exists():
            self.status_text = "맵 YAML 파일을 찾을 수 없습니다."
            self.update()
            return

        try:
            yaml_data = load_map_yaml(resolved_yaml_path)
            if resolved_pgm_path is None:
                resolved_pgm_path = resolve_map_path(
                    yaml_data.get("image"),
                    relative_to=resolved_yaml_path.parent,
                )
            image = (
                QImage(str(resolved_pgm_path))
                if resolved_pgm_path is not None
                else QImage()
            )
            self._apply_loaded_map(yaml_data=yaml_data, image=image)
        except Exception as exc:
            self.status_text = f"맵 로드 실패: {exc}"
            self.update()

    def load_map_from_assets(self, *, yaml_text, pgm_bytes, cache_key=None):
        next_cache_key = cache_key or (
            "assets",
            hash(yaml_text),
            hash(bytes(pgm_bytes or b"")),
        )
        if next_cache_key == self._map_cache_key:
            return

        self._reset_map_state(next_cache_key)

        try:
            yaml_data = parse_map_yaml_text(yaml_text)
            image = QImage.fromData(bytes(pgm_bytes or b""), "PGM")
            self._apply_loaded_map(yaml_data=yaml_data, image=image)
        except Exception as exc:
            self.status_text = f"맵 로드 실패: {exc}"
            self.update()

    def world_to_pixel(self, pose):
        if self._map_transform is None:
            return None
        return self._map_transform.world_to_pixel(pose)

    def pixel_to_world(self, pixel_point):
        if self._map_transform is None:
            return None
        return self._map_transform.pixel_to_world(pixel_point)

    def contains_world_pose(self, pose):
        if self._map_transform is None:
            return False
        return self._map_transform.contains_world_pose(pose)

    def view_to_world(self, view_point):
        pixel = self.view_to_pixel(view_point)
        return self.pixel_to_world(pixel)

    def view_to_pixel(self, view_point):
        if not self.map_loaded or self.map_image_size is None:
            return None
        target = self.image_target_rect()
        if target.isNull() or not target.contains(QPointF(view_point)):
            return None
        width, height = self.map_image_size
        pixel_x = ((float(view_point.x()) - target.left()) / target.width()) * width
        pixel_y = ((float(view_point.y()) - target.top()) / target.height()) * height
        return (int(round(pixel_x)), int(round(pixel_y)))

    def clear_map(self, status_text="맵 미수신"):
        self.map_loaded = False
        self.map_image_size = None
        self.status_text = status_text
        self._map_image = QImage()
        self._map_transform = None
        self._map_cache_key = None
        self.update()

    def image_target_rect(self):
        margin = 4.0
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

    def to_view_point(self, pixel_point, target):
        if pixel_point is None or self.map_image_size is None:
            return None
        width, height = self.map_image_size
        x, y = pixel_point
        return QPointF(
            target.left() + (float(x) / max(1, width)) * target.width(),
            target.top() + (float(y) / max(1, height)) * target.height(),
        )

    def draw_overlay(self, painter, target):
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            world_pose = self.view_to_world(event.position())
            if world_pose is not None:
                self.map_clicked.emit(world_pose)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            world_pose = self.view_to_world(event.position())
            if world_pose is not None:
                self.map_dragged.emit(world_pose)
        super().mouseMoveEvent(event)

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
                    self.status_text or "맵 미수신",
                )
                return

            target = self.image_target_rect()
            painter.drawImage(target, self._map_image)
            self.draw_overlay(painter, target)
        finally:
            painter.end()

    def _apply_loaded_map(self, *, yaml_data, image):
        if image.isNull():
            self.status_text = "맵 PGM 파일을 읽을 수 없습니다."
            self.update()
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
        self.update()

    def _reset_map_state(self, cache_key):
        self._map_cache_key = cache_key
        self.map_loaded = False
        self.map_image_size = None
        self.status_text = "맵 미수신"
        self._map_image = QImage()
        self._map_transform = None


__all__ = [
    "MapCanvasWidget",
    "MapTransform",
    "PROJECT_ROOT",
    "load_map_yaml",
    "parse_map_yaml_text",
    "resolve_map_path",
]
