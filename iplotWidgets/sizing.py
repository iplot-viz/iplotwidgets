"""
Sizing helpers so views follow the application font instead of pixel literals.

The tables and trees in this package sized their rows and columns in absolute
pixels. Two things go wrong with that. On an unscaled high-resolution panel the
values stay physically small, and a ``QHeaderView`` in ``Fixed`` resize mode
keeps whatever ``defaultSectionSize`` it resolved at construction, so when the
application font grows -- which is how MINT implements its UI scale -- the rows
do not and the text is clipped.

The pixel values are kept as they were and multiplied by how much the widget's
font has grown over the platform default, so at the default font every view
looks exactly as before on every platform, and :class:`FontScaledView`
re-applies the sizes whenever the font changes.
"""

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFontDatabase, QFontMetrics, QGuiApplication

#: Row height as a multiple of the font height. Leaves room for the cell
#: padding a style adds around the text.
DEFAULT_ROW_FACTOR = 1.6
#: Share of the available screen a window may take when its preferred size
#: does not fit.
SCREEN_SHARE = 0.9


def clamp_to_screen(widget, width: int, height: int, share: float = SCREEN_SHARE) -> None:
    """Resize ``widget`` to ``width`` x ``height``, or to ``share`` of its
    screen when that is smaller, so a window never opens partly off-screen."""
    screen = widget.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        widget.resize(width, height)
        return
    available = screen.availableGeometry()
    widget.resize(min(width, int(available.width() * share)),
                  min(height, int(available.height() * share)))


def font_scale(widget) -> float:
    """How much ``widget``'s font has grown over the platform default font.

    The platform font is what the application starts with, and
    ``QApplication.setFont`` does not change it, so this is 1.0 until the
    application enlarges its font.
    """
    base = QFontMetrics(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)).height()
    return widget.fontMetrics().height() / base if base > 0 else 1.0


def scaled_px(widget, pixels: int) -> int:
    """``pixels``, as tuned for the platform font, grown with ``widget``'s font."""
    return int(round(pixels * font_scale(widget)))


def row_height(widget, factor: float = DEFAULT_ROW_FACTOR) -> int:
    """A row height that fits ``widget``'s font with a little padding."""
    return int(widget.fontMetrics().height() * factor)


class FontScaledView:
    """Mixin keeping row heights and column widths tied to the current font.

    Mix in *before* the Qt view class so ``changeEvent`` resolves here first::

        class MyTable(FontScaledView, QTableView):
            COLUMN_WIDTHS = {0: 100}

    Subclasses must call :meth:`apply_font_metrics` *after* ``setModel``:
    ``setColumnWidth`` is a no-op on a view with no columns.
    """

    #: ``{column index: width in pixels at the platform font}``, applied as the
    #: initial width. The user can still drag columns; this only sets the
    #: starting point.
    COLUMN_WIDTHS = {}

    def apply_font_metrics(self):
        header = getattr(self, 'verticalHeader', None)
        if callable(header):
            vertical = header()
            if vertical is not None:
                # Fixed resize mode never revisits this on its own, which is why
                # a larger font used to clip the rows. The style's own default
                # stays the floor, so the rows keep their usual height until
                # the font outgrows it.
                if not hasattr(self, '_style_row_height'):
                    self._style_row_height = vertical.defaultSectionSize()
                vertical.setDefaultSectionSize(max(self._style_row_height, row_height(self)))
        for column, pixels in self.COLUMN_WIDTHS.items():
            self.setColumnWidth(column, scaled_px(self, pixels))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.apply_font_metrics()
