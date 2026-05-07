from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget


class KioskResidentPersonIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("kioskResidentPersonIcon")
        self.setFixedSize(56, 56)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(QColor("#2F855A"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawEllipse(QRectF(22, 10, 12, 12))

        shoulders = QPainterPath()
        shoulders.moveTo(14, 42)
        shoulders.cubicTo(14, 32, 21, 27, 28, 27)
        shoulders.cubicTo(35, 27, 42, 32, 42, 42)
        shoulders.lineTo(14, 42)
        painter.drawPath(shoulders)


__all__ = ["KioskResidentPersonIcon"]
