import math
from functools import lru_cache

from PySide6.QtCore import QAbstractAnimation, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from iplotWidgets.sizing import scaled_px

# The usual AI-feature mark: a large four-point star and a small one, in a 24x24 viewBox.
LARGE_STAR = 'M10 4.5Q11.3 11.7 18.5 13Q11.3 14.3 10 21.5Q8.7 14.3 1.5 13Q8.7 11.7 10 4.5z'
SMALL_STAR = 'M18.5 2Q19 5 22 5.5Q19 6 18.5 9Q18 6 15 5.5Q18 5 18.5 2z'

SVG_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
_LARGE_SVG = SVG_HEAD + '<path d="' + LARGE_STAR + '" fill="{color}"/></svg>'
_SMALL_SVG = SVG_HEAD + '<path d="' + SMALL_STAR + '" fill="{color}"/></svg>'

#: Star opacity range and period of the twinkle while the assistant works.
MIN_OPACITY = 0.35
PERIOD_MS = 1200
#: Frames per period, about 3 a second: next to an OpenGL view each one composes the whole window again.
STEPS = 4


@lru_cache(maxsize=64)
def _cached_renderer(template: str, rgba: int):
    # Parsing the SVG on every frame of the animation would be wasted work: one renderer per colour.
    color = QColor.fromRgba(rgba)
    # The alpha goes in a separate attribute: SVG colours do not take it.
    svg = template.format(color=color.name(QColor.NameFormat.HexRgb))
    if color.alpha() < 255:
        svg = svg.replace('<path ', '<path opacity="%.3f" ' % (color.alphaF()))
    return QSvgRenderer(svg.encode('utf-8'))


def svg_icon(template: str, color, size: int = 24) -> QIcon:
    """An icon drawn from an SVG ``template`` with a ``{color}`` field, sharp at the screen's pixel ratio."""
    color = QColor(color)
    screen = QGuiApplication.primaryScreen()
    ratio = max(1.0, screen.devicePixelRatio()) if screen is not None else 1.0
    pixmap = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _cached_renderer(template, color.rgba()).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def paint_assistant_icon(painter: QPainter, rect: QRectF, color: QColor, large_opacity: float = 1.0,
                         small_opacity: float = 1.0):
    """Draw the two stars inside ``rect`` (the 24x24 viewBox scaled to fit)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = painter.opacity()
    painter.setOpacity(base * large_opacity)
    _cached_renderer(_LARGE_SVG, color.rgba()).render(painter, rect)
    painter.setOpacity(base * small_opacity)
    _cached_renderer(_SMALL_SVG, color.rgba()).render(painter, rect)
    painter.restore()


def assistant_icon(color, size: int = 24) -> QIcon:
    """An icon for a toolbar button or menu entry. ``color`` is normally the palette text colour."""
    return svg_icon(SVG_HEAD + '<path d="' + LARGE_STAR + ' ' + SMALL_STAR + '" fill="{color}"/></svg>', color, size)


class AssistantIcon(QWidget):
    """The assistant mark in the highlight colour on an alternate-base disc; while active its stars twinkle in turn."""

    def __init__(self, parent=None, size: int = 24):
        super().__init__(parent)
        self._base_size = size
        self._active = False
        self._phase = 0.0
        self._colors = None
        # A linear phase from 0 to 1, looped; each star's opacity follows a cosine of it, half a period
        # apart, so one brightens as the other fades and both are slowest at either end.
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

    def set_colors(self, disc: QColor, stars: QColor):
        """Colours to use instead of the palette's alternate base and highlight."""
        self._colors = (QColor(disc), QColor(stars))
        self.update()

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
            self._phase = 0.0
        self.update()

    def is_animating(self) -> bool:
        return self._breath.state() == QAbstractAnimation.State.Running

    def _on_phase(self, phase):
        phase = int(float(phase) * STEPS) / STEPS
        if phase != self._phase:
            self._phase = phase
            self.update()

    @staticmethod
    def _opacity(phase: float) -> float:
        return MIN_OPACITY + (1.0 - MIN_OPACITY) * 0.5 * (1.0 + math.cos(2.0 * math.pi * phase))

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
        disc, stars = self._colors or (palette.color(QPalette.ColorRole.AlternateBase),
                                       palette.color(QPalette.ColorRole.Highlight))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(disc)
        painter.drawEllipse(rect)
        rect = rect.adjusted(rect.width() * 0.2, rect.height() * 0.2, -rect.width() * 0.2, -rect.height() * 0.2)
        large = self._opacity(self._phase) if self._active else 1.0
        small = self._opacity(self._phase + 0.5) if self._active else 1.0
        paint_assistant_icon(painter, rect, stars, large, small)
        painter.end()
