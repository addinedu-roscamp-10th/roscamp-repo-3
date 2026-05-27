import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from ui.utils.widgets.drive_route_overlay import draw_drive_route_markers


class _CanvasStub:
    @staticmethod
    def to_view_point(pixel, target):
        _ = target
        x, y = pixel
        return QPointF(float(x), float(y))


def test_drive_route_overlay_draws_open_lines_without_inherited_fill_brush():
    image = QImage(120, 120, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))

    painter = QPainter(image)
    try:
        painter.setBrush(QColor("#FF0000"))
        draw_drive_route_markers(
            _CanvasStub(),
            painter,
            QRectF(0, 0, 120, 120),
            [
                {
                    "route_pixel_points": [(10, 10), (90, 10), (50, 90)],
                    "target_route_index": None,
                }
            ],
        )
    finally:
        painter.end()

    assert image.pixelColor(50, 30).name().upper() == "#FFFFFF"
