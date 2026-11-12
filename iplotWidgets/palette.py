"""Colours taken from a palette, so that the widgets draw in a dark one what they draw in a light one."""

from typing import Optional

from PySide6.QtGui import QColor, QGuiApplication, QPalette


def is_dark(palette: Optional[QPalette] = None) -> bool:
    """Whether a palette, the application's by default, draws light text on a dark window."""
    palette = QGuiApplication.palette() if palette is None else palette
    return (palette.color(QPalette.ColorRole.Window).lightness()
            < palette.color(QPalette.ColorRole.WindowText).lightness())


def blend(a, b, t: float) -> QColor:
    """The colour a fraction `t` of the way from colour `a` to colour `b`."""
    a, b = QColor(a), QColor(b)
    return QColor.fromRgbF(*(x + (y - x) * t for x, y in zip(a.getRgbF()[:3], b.getRgbF()[:3])))
