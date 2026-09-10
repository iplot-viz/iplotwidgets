"""
Sizing helpers so views follow the application font instead of pixel literals.

The tables and trees in this package sized their rows and columns in absolute
pixels. Two things go wrong with that. On an unscaled high-resolution panel the
values stay physically small, and a ``QHeaderView`` in ``Fixed`` resize mode
keeps whatever ``defaultSectionSize`` it resolved at construction, so when the
application font grows -- which is how MINT implements its UI scale -- the rows
do not and the text is clipped.

Expressing the same intent in characters and font height fixes both: the numbers
mean "about twelve characters wide" rather than "one hundred pixels", and
:class:`FontScaledView` re-applies them whenever the font changes.
"""

from PySide6.QtCore import QEvent

#: Row height as a multiple of the font height. Leaves room for the cell
#: padding a style adds around the text.
DEFAULT_ROW_FACTOR = 1.6


def char_width(widget, chars: int) -> int:
    """Width of roughly ``chars`` characters in ``widget``'s font."""
    metrics = widget.fontMetrics()
    # averageCharWidth can report 0 with an unusual font; fall back to 'x'.
    unit = metrics.averageCharWidth() or metrics.horizontalAdvance('x') or 8
    return int(unit * chars)


def row_height(widget, factor: float = DEFAULT_ROW_FACTOR) -> int:
    """A row height that fits ``widget``'s font with a little padding."""
    return int(widget.fontMetrics().height() * factor)


class FontScaledView:
    """Mixin keeping row heights and column widths tied to the current font.

    Mix in *before* the Qt view class so ``changeEvent`` resolves here first::

        class MyTable(FontScaledView, QTableView):
            COLUMN_CHARS = {0: 14}

    Subclasses must call :meth:`apply_font_metrics` *after* ``setModel``:
    ``setColumnWidth`` is a no-op on a view with no columns.
    """

    #: ``{column index: width in characters}``, applied as the initial width.
    #: The user can still drag columns; this only sets the starting point.
    COLUMN_CHARS = {}

    def apply_font_metrics(self):
        header = getattr(self, 'verticalHeader', None)
        if callable(header):
            vertical = header()
            if vertical is not None:
                # Fixed resize mode never revisits this on its own, which is why
                # a larger font used to clip the rows.
                vertical.setDefaultSectionSize(row_height(self))
        for column, chars in self.COLUMN_CHARS.items():
            self.setColumnWidth(column, char_width(self, chars))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.apply_font_metrics()
