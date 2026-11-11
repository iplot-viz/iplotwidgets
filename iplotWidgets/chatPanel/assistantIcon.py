import math
from functools import lru_cache

from PySide6.QtCore import QAbstractAnimation, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from iplotWidgets.sizing import scaled_px

COIL_PATH = 'M8 4h3.5c5.2 0 8.5 3.6 8.5 8s-3.3 8-8.5 8h-1.1L8 22.5V20z'
SPARK_PATH = ('M14 8.5c.4 2.4 1.1 3.1 3.5 3.5-2.4.4-3.1 1.1-3.5 3.5-.4-2.4-1.1-3.1-3.5-3.5 '
              '2.4-.4 3.1-1.1 3.5-3.5z')

_SVG_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
_COIL_SVG = (_SVG_HEAD + '<path d="' + COIL_PATH + '" fill="none" stroke="{color}" stroke-width="1.8" '
             'stroke-linejoin="round" stroke-linecap="round"/></svg>')
_SPARK_SVG = _SVG_HEAD + '<path d="' + SPARK_PATH + '" fill="{color}"/></svg>'

#: Spark opacity range and period of the "breathing" animation.
MIN_OPACITY = 0.4
PERIOD_MS = 1200


@lru_cache(maxsize=32)
def _cached_renderer(template: str, rgba: int):
    # Parsing the SVG on every frame of the animation would be wasted work: one renderer per colour.
    color = QColor.fromRgba(rgba)
    # The alpha goes in a separate attribute: SVG colours do not take it.
    svg = template.format(color=color.name(QColor.NameFormat.HexRgb))
    if color.alpha() < 255:
        svg = svg.replace('<path ', '<path opacity="%.3f" ' % (color.alphaF()))
    return QSvgRenderer(svg.encode('utf-8'))


def paint_assistant_icon(painter: QPainter, rect: QRectF, coil: QColor, spark: QColor,
                         spark_opacity: float = 1.0):
    """Draw the coil and the spark inside ``rect`` (the 24x24 viewBox scaled to fit)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _cached_renderer(_COIL_SVG, coil.rgba()).render(painter, rect)
    painter.setOpacity(painter.opacity() * spark_opacity)
    _cached_renderer(_SPARK_SVG, spark.rgba()).render(painter, rect)
    painter.restore()


def assistant_icon(color, size: int = 24) -> QIcon:
    """An icon for a toolbar button. ``color`` is normally the palette text colour."""
    color = QColor(color)
    screen = QGuiApplication.primaryScreen()
    ratio = max(1.0, screen.devicePixelRatio()) if screen is not None else 1.0
    pixmap = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    paint_assistant_icon(painter, QRectF(0, 0, size, size), color, color)
    painter.end()
    return QIcon(pixmap)


class AssistantIcon(QWidget):
    """The assistant mark on a disc. While active its spark breathes; the coil never moves."""

    def __init__(self, parent=None, size: int = 24):
        super().__init__(parent)
        self._base_size = size
        self._active = False
        self._opacity = 1.0
        # A linear phase from 0 to 1, looped; the opacity follows a cosine of it, so the
        # spark is slowest at full and at dim opacity, like breathing.
        self._breath = QVariantAnimation(self)
        self._breath.setStartValue(0.0)
        self._breath.setEndValue(1.0)
        self._breath.setDuration(PERIOD_MS)
        self._breath.setLoopCount(-1)
        self._breath.valueChanged.connect(self._on_phase)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._apply_size()

    def _apply_size(self):
        side = scaled_px(self, self._base_size)
        self.setFixedSize(side, side)

    def sizeHint(self):
        return self.size()

    def set_active(self, active: bool):
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        if active:
            if self.isVisible():
                self._breath.start()
        else:
            self._breath.stop()
            self._opacity = 1.0
        self.update()

    def is_animating(self) -> bool:
        return self._breath.state() == QAbstractAnimation.State.Running

    def _on_phase(self, phase):
        self._opacity = MIN_OPACITY + (1.0 - MIN_OPACITY) * 0.5 * (1.0 + math.cos(2.0 * math.pi * float(phase)))
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._active and self._breath.state() != QAbstractAnimation.State.Running:
            self._breath.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        # A hidden icon needs no frames: nothing runs while the panel is closed.
        self._breath.stop()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.FontChange:
            self._apply_size()

    def paintEvent(self, event):
        palette = self.palette()
        text = palette.color(QPalette.ColorRole.Text)
        spark = palette.color(QPalette.ColorRole.Highlight) if self._active else text
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.AlternateBase))
        painter.drawEllipse(rect)
        rect = rect.adjusted(rect.width() * 0.16, rect.height() * 0.16, -rect.width() * 0.16, -rect.height() * 0.16)
        paint_assistant_icon(painter, rect, text, spark, self._opacity if self._active else 1.0)
        painter.end()
