import math
import os
import re

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRect,
                            QRectF, QSize, Qt, Signal)
from PySide6.QtGui import QColor, QFontDatabase, QFontMetricsF, QPainter, QPalette, QTextLayout, QTextOption
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout,
                               QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QToolButton,
                               QVBoxLayout, QWidget)

from iplotWidgets.chatPanel.assistantIcon import SVG_HEAD, AssistantIcon, assistant_icon, svg_icon
from iplotWidgets.sizing import scaled_px

#: Share of the conversation width a bubble may take.
BUBBLE_SHARE = 0.85
#: Options beyond this many get a scroll area instead of growing the card.
MAX_VISIBLE_OPTIONS = 8
MAX_INPUT_LINES = 5
#: How long a new message, card or note takes to fade in.
FADE_IN_MS = 200

_ROLE = QPalette.ColorRole

# Drawn like the iplotlib tool bar icons: 24x24 with round 1.8 strokes.
_STROKES = '<g fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
_FRAME = '<path d="M10 5H6.5A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19h11a1.5 1.5 0 0 0 1.5-1.5V14"/>'
POP_OUT_SVG = SVG_HEAD + _STROKES + _FRAME + '<path d="M14 5h5v5"/><path d="M19 5l-7 7"/></g></svg>'
POP_IN_SVG = SVG_HEAD + _STROKES + _FRAME + '<path d="M12 7v5h5"/><path d="M12 12l7-7"/></g></svg>'
CLOSE_SVG = SVG_HEAD + _STROKES + '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/></g></svg>'
SEND_SVG = SVG_HEAD + _STROKES + '<path d="M12 18.5v-13M6.5 11 12 5.5l5.5 5.5"/></g></svg>'
STOP_SVG = SVG_HEAD + '<rect x="7" y="7" width="10" height="10" rx="2" fill="{color}"/></svg>'
ATTACH_SVG = SVG_HEAD + _STROKES + ('<path d="M15.5 6.5 8.3 13.7a2 2 0 0 0 2.8 2.8l7.4-7.4a4 4 0 0 0-5.7-5.7'
                                     'L5.4 10.8a6 6 0 0 0 8.5 8.5l6.3-6.3"/></g></svg>')

# A host style sheet gives text edits a frame, padding and a background, and every plain widget a
# background: inside the panel those would draw boxes in boxes and cut the last line of a message.
_PLAIN_TEXT = '{kind} {{ border: none; padding: 0; margin: 0; background: transparent; {colors} }}'
_PANEL_STYLE = '''
*[chatPlain="true"] {{ background: transparent; border: none; }}
QCheckBox#chatOption {{ background: transparent; }}
QCheckBox#chatOption::indicator {{ width: {box}px; height: {box}px; border: 1px solid {line}; border-radius: 3px;
                                   background: {field}; }}
QCheckBox#chatOption::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QCheckBox#chatOption::indicator:disabled {{ background: {background}; }}
QToolButton#chatHeaderButton {{ background: transparent; border: none; border-radius: 4px; padding: 3px; }}
QToolButton#chatHeaderButton:hover {{ background: {hover}; }}
QToolButton#chatHeaderButton:pressed {{ background: {line}; }}
QPushButton#chatSend, QPushButton#chatStop {{ background: {accent}; border: none; padding: 0; }}
QPushButton#chatSend:disabled {{ background: {line}; }}
'''


def mix(a: QColor, b: QColor, amount: float) -> QColor:
    return QColor.fromRgbF(a.redF() + (b.redF() - a.redF()) * amount, a.greenF() + (b.greenF() - a.greenF()) * amount,
                           a.blueF() + (b.blueF() - a.blueF()) * amount)


class Scheme:
    """The panel's colours, mixed from the host's window, text and selection colours only.

    A theme style sheet sets those and may leave Base as the platform had it (white under a dark theme).
    """

    def __init__(self, palette: QPalette = None):
        self.update(palette or QPalette())

    def update(self, palette: QPalette):
        # The active group: some platforms grey the highlight out while the window is inactive.
        def color(role):
            return palette.color(QPalette.ColorGroup.Active, role)

        window, text = color(_ROLE.Window), color(_ROLE.WindowText)
        dark = window.lightnessF() < 0.5
        paper = QColor('#000000' if dark else '#ffffff')
        self.text = text
        self.background = mix(window, paper, 0.12 if dark else 0.6)
        self.field = mix(window, paper, 0.2 if dark else 1.0)
        self.bubble = mix(self.background, text, 0.07)
        self.hover = mix(self.background, text, 0.1)
        self.line = mix(self.background, text, 0.22)
        self.hint = mix(self.background, text, 0.55)
        self.accent = color(_ROLE.Highlight)
        self.on_accent = color(_ROLE.HighlightedText)

    def key(self) -> tuple:
        """Changes when any colour of the scheme does."""
        return self.text.rgba(), self.background.rgba(), self.accent.rgba(), self.on_accent.rgba()


def _plain(widget: QWidget) -> QWidget:
    widget.setProperty('chatPlain', True)
    return widget


def _small_font(widget, factor: float = 0.85):
    font = widget.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * factor)
    elif font.pixelSize() > 0:
        font.setPixelSize(max(1, int(font.pixelSize() * factor)))
    return font


def _literal(text: str) -> str:
    # Button and check box texts read '&' as a keyboard shortcut marker.
    return text.replace('&', '&&')


class _FlowLayout(QLayout):
    """Left-to-right layout that wraps onto new rows, so it never forces a width."""

    def __init__(self, parent=None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._lay_out(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._lay_out(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _lay_out(self, rect, apply):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            # An entry wider than the panel takes its width and grows down instead of widening it.
            width = min(hint.width(), max(area.width(), 1))
            height = item.heightForWidth(width) if item.hasHeightForWidth() else hint.height()
            if x > area.x() and x + width > area.right() + 1:
                x = area.x()
                y += row_height + self._gap
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), QSize(width, height)))
            x += width + self._gap
            row_height = max(row_height, height)
        return y + row_height - rect.y() + m.bottom()


class _TextView(QTextEdit):
    """Read-only selectable text that wraps anywhere, where a QLabel breaks only at words and widens with a long name.

    Height through heightForWidth: one layout pass; a height set afterwards needs a second, which some platforms delay.
    """

    def __init__(self, text: str, parent=None, bold: bool = False, mono: bool = False, object_name='chatText',
                 on_accent: bool = False):
        super().__init__(parent)
        self._text = text
        self._heights = {}
        self._measure = None
        self._font_key = None
        self._colors = None
        self.on_accent = on_accent
        self.setObjectName(object_name)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(_PLAIN_TEXT.format(kind='QTextEdit', colors=''))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(0)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        if mono:
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            if self.font().pointSizeF() > 0:
                font.setPointSizeF(self.font().pointSizeF())
            self.setFont(font)
        if bold:
            font = self.font()
            font.setBold(True)
            self.setFont(font)
        self.setPlainText(text)

    def apply_scheme(self, scheme: Scheme):
        # Text on the accent colour swaps the roles, selection included, or a selection would vanish.
        if self.on_accent:
            text, selection, selected = scheme.on_accent, scheme.on_accent, scheme.accent
        else:
            text, selection, selected = scheme.text, scheme.accent, scheme.on_accent
        colors = (f'color: {text.name()}; selection-background-color: {selection.name()}; '
                  f'selection-color: {selected.name()};')
        if colors == self._colors:
            return
        self._colors = colors
        palette = QPalette(self.palette())
        palette.setColor(_ROLE.Text, text)
        palette.setColor(_ROLE.Highlight, selection)
        palette.setColor(_ROLE.HighlightedText, selected)
        self.setPalette(palette)
        # The palette alone would lose to a host style sheet's colours.
        style = _PLAIN_TEXT.format(kind='QTextEdit', colors=colors)
        if style != self.styleSheet():
            self.setStyleSheet(style)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width: int) -> int:
        height = self._heights.get(width)
        if height is None:
            # Measured on a copy, so the text on screen is not laid out again for every width asked.
            if self._measure is None:
                self._measure = self.document().clone(self)
                self._measure.setDocumentMargin(self.document().documentMargin())  # clone() leaves it out
            # Whatever a style still puts around the viewport comes on top of the text.
            chrome_w = max(0, self.width() - self.viewport().width())
            chrome_h = max(0, self.height() - self.viewport().height())
            self._measure.setTextWidth(max(width - chrome_w, 1))
            height = int(math.ceil(self._measure.size().height())) + chrome_h
            if len(self._heights) > 32:  # dragging a splitter asks for many widths
                self._heights.clear()
            self._heights[width] = height
        return height

    def natural_width(self) -> int:
        metrics = self.fontMetrics()
        return max((metrics.horizontalAdvance(line) for line in self._text.split('\n')), default=0) + 4

    def sizeHint(self):
        width = self.natural_width()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QSize(scaled_px(self, 24), self.fontMetrics().lineSpacing())

    def changeEvent(self, event):
        super().changeEvent(event)
        # A new font re-wraps the lines at the same width. Host style sheets send StyleChange on every edit, so
        # re-measure only when the font key changed (this text's own style sheet keeps padding and border at zero).
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            key = self.font().key()
            if key != self._font_key:
                self._font_key = key
                self._heights.clear()
                self._measure = None
                self.updateGeometry()

    def wheelEvent(self, event):
        # Nothing to scroll here; let the conversation scroll instead.
        event.ignore()


class _InputEdit(QPlainTextEdit):
    submitRequested = Signal()
    recallRequested = Signal()
    escapePressed = Signal()
    focusChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(_PLAIN_TEXT.format(kind='QPlainTextEdit', colors=''))
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._fit_height())
        self._fit_height()

    def apply_scheme(self, scheme: Scheme):
        palette = QPalette(self.palette())
        palette.setColor(_ROLE.PlaceholderText, scheme.hint)
        self.setPalette(palette)
        style = _PLAIN_TEXT.format(kind='QPlainTextEdit', colors=f'color: {scheme.text.name()};')
        if style != self.styleSheet():
            self.setStyleSheet(style)

    def _fit_height(self):
        wanted = int(math.ceil(self.document().size().height()))
        lines = max(1, min(MAX_INPUT_LINES, wanted))
        # Below the limit the height always fits, so a bar would only be noise.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if wanted > MAX_INPUT_LINES
                                        else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chrome = 2 * self.frameWidth() + int(2 * self.document().documentMargin())
        height = lines * self.fontMetrics().lineSpacing() + chrome
        if height != self.height():
            self.setFixedHeight(height)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit_height()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focusChanged.emit(True)

    def dragEnterEvent(self, event):
        # A file is for the panel to attach (see ChatPanel.set_attachable), not text: ignored here, the drag
        # goes on to the panel, and this box gets no move or drop of it.
        if event.mimeData().hasUrls():
            event.ignore()
        else:
            super().dragEnterEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusChanged.emit(False)

    def keyPressEvent(self, event):
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not shift:
            self.submitRequested.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            return
        if key == Qt.Key.Key_Up and not self.toPlainText() and not event.modifiers():
            self.recallRequested.emit()
            return
        super().keyPressEvent(event)


class _Surface(QFrame):
    """A rounded panel in two of the scheme's colours, named by attribute (``fill``, ``border``)."""

    def __init__(self, scheme: Scheme, fill: str, border: str = None, radius=10, parent=None):
        super().__init__(parent)
        _plain(self)
        self._scheme = scheme
        self._fill = fill
        self._border = border
        self._radius = radius
        self._emphasis = False

    def set_emphasis(self, emphasis: bool):
        """Outline in the accent colour, as a focused input is."""
        if emphasis != self._emphasis:
            self._emphasis = emphasis
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = 'accent' if self._emphasis else self._border
        if border is None:
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setPen(getattr(self._scheme, border))
        painter.setBrush(getattr(self._scheme, self._fill))
        radius = scaled_px(self, self._radius)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.end()


class _HintLabel(QLabel):
    """A label in the scheme's low-contrast hint colour."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _plain(self)
        # Status and notes carry error messages; QLabel would guess rich text from a '<'.
        self.setTextFormat(Qt.TextFormat.PlainText)

    def apply_scheme(self, scheme: Scheme):
        style = f'color: {scheme.hint.name()};'
        if style != self.styleSheet():
            self.setStyleSheet(style)


def _wrap_option(alignment=Qt.AlignmentFlag.AlignLeft) -> QTextOption:
    option = QTextOption(alignment)
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    return option


def _wrapped_height(text: str, font, width: float) -> float:
    """Height of ``text`` wrapped to ``width`` as QPainter.drawText draws it with _wrap_option()."""
    layout = QTextLayout(text, font)
    layout.setTextOption(_wrap_option())
    layout.beginLayout()
    height = 0.0
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(width, 1.0))
        height += line.height()
    layout.endLayout()
    return height


class _Chip(QPushButton):
    """A flat suggestion button with a rounded outline. A text wider than the room wraps; it is never cut."""

    def __init__(self, text, scheme: Scheme, parent=None):
        super().__init__(text, parent)
        self._scheme = scheme
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        # A push button is as wide as its text at least and one line high; this one narrows to the room there
        # is and grows by the lines its text wraps onto.
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _padding(self):
        return scaled_px(self, 10), scaled_px(self, 4) + 1

    def sizeHint(self):
        across, down = self._padding()
        metrics = QFontMetricsF(self.font())
        # Rounded up with a pixel to spare: at 150 % the text takes a fraction more than its whole-pixel width.
        return QSize(math.ceil(metrics.horizontalAdvance(self.text())) + 2 * across + 1,
                     math.ceil(metrics.height()) + 2 * down)

    def minimumSizeHint(self):
        return QSize(scaled_px(self, 24), self.sizeHint().height())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        across, down = self._padding()
        return math.ceil(_wrapped_height(self.text(), self.font(), width - 2 * across)) + 2 * down

    def paintEvent(self, event):
        scheme = self._scheme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hot = self.underMouse() or self.hasFocus()
        painter.setBrush(scheme.bubble if self.underMouse() else Qt.BrushStyle.NoBrush)
        painter.setPen(scheme.accent if hot else scheme.line)
        # The corners of a one-line chip, also when it wraps onto more lines.
        radius = min(rect.height(), self.sizeHint().height()) / 2
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(scheme.text)
        across, down = self._padding()
        painter.drawText(QRectF(self.rect()).adjusted(across, down, -across, -down), self.text(),
                         _wrap_option(Qt.AlignmentFlag.AlignCenter))
        painter.end()


class _IconButton(QPushButton):
    """A round button showing a stroke icon in the colour that goes on the accent."""

    def __init__(self, svg: str, tip: str, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._svg = svg
        self._color = QColor('#ffffff')
        self._apply_size()

    def apply_scheme(self, scheme: Scheme):
        self._color = scheme.on_accent
        self._apply_size()

    def _apply_size(self):
        side = scaled_px(self, 28)
        self.setFixedSize(side, side)
        icon = scaled_px(self, 18)
        self.setIconSize(QSize(icon, icon))
        self.setIcon(svg_icon(self._svg, self._color, icon))
        style = f'border-radius: {side // 2}px;'
        if style != self.styleSheet():
            self.setStyleSheet(style)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._apply_size()


class _TitleIcon(QLabel):
    """The assistant mark before the title, drawn in the text colour like the host's button for the panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _plain(self)
        self._color = self.palette().color(_ROLE.WindowText)
        self._draw()

    def apply_scheme(self, scheme: Scheme):
        self._color = scheme.text
        self._draw()

    def _draw(self):
        size = scaled_px(self, 16)
        self.setPixmap(assistant_icon(self._color, size).pixmap(QSize(size, size)))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._draw()


class _HeaderButton(QToolButton):
    def __init__(self, svg: str, tip: str, parent=None):
        super().__init__(parent)
        self.setObjectName('chatHeaderButton')
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = self.palette().color(_ROLE.WindowText)
        self.set_icon(svg, tip)

    def apply_scheme(self, scheme: Scheme):
        self._color = scheme.text
        self._draw()

    def set_icon(self, svg: str, tip: str):
        self._svg = svg
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self._draw()

    def _draw(self):
        size = scaled_px(self, 16)
        self.setIconSize(QSize(size, size))
        self.setIcon(svg_icon(self._svg, self._color, size))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._draw()


class _Conversation(QWidget):
    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class _Card:
    def __init__(self):
        self.buttons = {}
        self.options = []
        self.note = None


class ChatPanel(QWidget):
    """A conversation view with an input box; it knows nothing about who answers."""

    messageSubmitted = Signal(str)
    cardActionTriggered = Signal(int, str, list)
    stopRequested = Signal()
    # Enter with nothing typed: the host may take it as "yes" to what is on screen (e.g. Apply).
    emptySubmitted = Signal()
    # The panel hid itself: the host may uncheck its toggle.
    closeRequested = Signal()
    # True for a window of its own, False to go back. The host moves it, then calls set_detached.
    detachRequested = Signal(bool)
    # A file the user attached (see set_attachable); what it means is up to the host.
    fileAttached = Signal(str)
    # The user left out the file shown above the input box (see set_attachment).
    attachmentRemoved = Signal()

    def __init__(self, parent=None, title: str = 'Assistant'):
        super().__init__(parent)
        self._next_id = 1
        self._items = []
        self._bubbles = []
        self._cards = {}
        self._last_kind = None
        self._busy = False
        self._preparing = False
        self._input_enabled = True
        self._last_message = ''
        self._stick_to_bottom = True
        self._suggestions = []
        self._suggest_anytime = False
        self._detached = False
        self._restyling = False
        self._attach_filter = ''
        self._attach_suffixes = ()
        self._attach_dir = ''
        self._scheme = Scheme(self.palette())
        self._scheme_key = None

        self.setMinimumWidth(scaled_px(self, 280))
        gap = scaled_px(self, 6)
        pad = scaled_px(self, 10)

        self._header = _plain(QWidget())
        self._header.setObjectName('chatHeader')
        self._title_icon = _TitleIcon()
        self._title_icon.setObjectName('chatTitleIcon')
        self._title = _plain(QLabel(title))
        self._title.setObjectName('chatTitle')
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)
        self.pop_button = _HeaderButton(POP_OUT_SVG, self.tr('Open in a separate window'))
        self.pop_button.clicked.connect(lambda *_: self.detachRequested.emit(not self._detached))
        self.pop_button.setVisible(False)
        self.close_button = _HeaderButton(CLOSE_SVG, self.tr('Close'))
        self.close_button.clicked.connect(lambda *_: self._close())
        header = QHBoxLayout(self._header)
        header.setContentsMargins(pad + 2, gap, gap, gap)
        header.setSpacing(scaled_px(self, 2))
        header.addWidget(self._title_icon)
        header.addSpacing(scaled_px(self, 4))
        header.addWidget(self._title, 1)
        header.addWidget(self.pop_button)
        header.addWidget(self.close_button)

        self._content = _plain(_Conversation())
        self._content.setObjectName('chatContent')
        self._items_layout = QVBoxLayout(self._content)
        self._items_layout.setContentsMargins(0, gap, scaled_px(self, 4), gap)
        self._items_layout.setSpacing(gap)
        # Room above the messages: none, except while preparing with no messages yet (see _place_progress).
        self._items_layout.addStretch(0)
        self._busy_row = self._build_busy_row()
        self._items_layout.addWidget(self._busy_row)
        self._progress = self._build_progress_row()
        self._items_layout.addWidget(self._progress)
        self._items_layout.addStretch(1)
        self._content.resized.connect(self._update_bubble_limits)

        self._scroll = _plain(QScrollArea())
        self._scroll.setObjectName('chatScroll')
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._content)
        # The panel paints the background; setWidget turns autofill on.
        self._content.setAutoFillBackground(False)
        _plain(self._scroll.viewport()).setAutoFillBackground(False)
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(self._on_range_changed)
        bar.valueChanged.connect(self._on_scrolled)

        self._chips = _plain(QWidget())
        self._chips.setObjectName('chatChips')
        self._chips_layout = _FlowLayout(self._chips, spacing=gap)
        self._chips.setVisible(False)

        self.input = _InputEdit()
        self.input.setObjectName('chatInput')
        self.input.submitRequested.connect(self._submit)
        self.input.recallRequested.connect(self._recall)
        self.input.escapePressed.connect(self._on_escape)
        self.send_button = _IconButton(SEND_SVG, self.tr('Send (Enter)'), 'chatSend')
        self.send_button.clicked.connect(lambda *_: self._submit())
        self.stop_button = _IconButton(STOP_SVG, self.tr('Stop (Esc)'), 'chatStop')
        self.stop_button.clicked.connect(lambda *_: self.stopRequested.emit())
        self.stop_button.setVisible(False)
        self.attach_button = _HeaderButton(ATTACH_SVG, self.tr('Attach a file'))
        self.attach_button.clicked.connect(lambda *_: self._choose_file())
        self.attach_button.setVisible(False)

        self._attachment = _plain(QWidget())
        self._attachment.setObjectName('chatAttachment')
        clip = _HeaderButton(ATTACH_SVG, '')
        clip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        clip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._attachment_label = _HintLabel()
        self.remove_attachment_button = _HeaderButton(CLOSE_SVG, self.tr('Leave the file out'))
        self.remove_attachment_button.clicked.connect(lambda *_: self.attachmentRemoved.emit())
        attachment = QHBoxLayout(self._attachment)
        attachment.setContentsMargins(0, 0, 0, 0)
        attachment.setSpacing(scaled_px(self, 2))
        attachment.addWidget(clip)
        attachment.addWidget(self._attachment_label, 1)
        attachment.addWidget(self.remove_attachment_button)
        self._attachment.setVisible(False)

        self._composer = _Surface(self._scheme, 'field', 'line', radius=10)
        self._composer.setObjectName('chatComposer')
        self.input.focusChanged.connect(self._composer.set_emphasis)
        composer = QHBoxLayout(self._composer)
        composer.setContentsMargins(pad, scaled_px(self, 5), scaled_px(self, 5), scaled_px(self, 5))
        composer.setSpacing(gap)
        composer.addWidget(self.attach_button, 0, Qt.AlignmentFlag.AlignBottom)
        composer.addWidget(self.input, 1, Qt.AlignmentFlag.AlignVCenter)
        composer.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        composer.addWidget(self.stop_button, 0, Qt.AlignmentFlag.AlignBottom)

        self._status = _HintLabel()
        self._status.setObjectName('chatStatus')
        self._status.setFont(_small_font(self._status))
        self._status.setVisible(False)

        body = QVBoxLayout()
        body.setContentsMargins(pad, 0, pad, pad)
        body.setSpacing(gap)
        body.addWidget(self._scroll, 1)
        body.addWidget(self._chips)
        body.addWidget(self._attachment)
        body.addWidget(self._composer)
        body.addWidget(self._status)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)  # room for the line under the header
        layout.addWidget(self._header)
        layout.addLayout(body, 1)
        self._restyle()

    def _build_busy_row(self):
        row = _plain(QWidget())
        row.setObjectName('chatBusy')
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled_px(self, 6))
        self._busy_icon = AssistantIcon(size=28)
        self._busy_label = _HintLabel()
        self._busy_label.setObjectName('chatBusyText')
        self._busy_label.setWordWrap(True)
        self._busy_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._busy_icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._busy_label, 1, Qt.AlignmentFlag.AlignVCenter)
        row.setVisible(False)
        return row

    def _build_progress_row(self):
        row = _plain(QWidget())
        row.setObjectName('chatProgress')
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled_px(self, 8))
        self._progress_icon = AssistantIcon(size=36)
        self._progress_label = _HintLabel()
        self._progress_label.setObjectName('chatProgressText')
        self._progress_label.setWordWrap(True)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._progress_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._progress_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._progress_label)
        row.setVisible(False)
        return row

    def _place_progress(self):
        # Alone, what the host prepares sits in the middle of the conversation; after messages, where the next
        # answer will go.
        self._items_layout.setStretch(0, 1 if self._preparing and not self._items else 0)

    def _restyle(self):
        """Work the colours out again from the host's, and hand them to every part."""
        # Setting the style sheet re-polishes the panel, which comes back here.
        if self._restyling:
            return
        self._restyling = True
        try:
            self.ensurePolished()
            scheme = self._scheme
            scheme.update(self.palette())
            style = _PANEL_STYLE.format(hover=scheme.hover.name(), line=scheme.line.name(),
                                        accent=scheme.accent.name(), field=scheme.field.name(),
                                        background=scheme.background.name(), box=scaled_px(self, 13))
            if style != self.styleSheet():
                self.setStyleSheet(style)
            # A host style sheet sends this to the panel on every change: the parts get the colours
            # only when they changed (parts made later take them when made).
            key = scheme.key()
            if key != self._scheme_key:
                self._scheme_key = key
                for kind in (_TextView, _InputEdit, _HintLabel, _IconButton, _HeaderButton, _TitleIcon):
                    for widget in self.findChildren(kind):
                        widget.apply_scheme(scheme)
                for icon in self.findChildren(AssistantIcon):
                    icon.set_colors(scheme.bubble, scheme.accent)
            # Repainting the panel repaints every part inside it.
            self.update()
        finally:
            self._restyling = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.setMinimumWidth(scaled_px(self, 280))
        elif event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._restyle()

    def showEvent(self, event):
        super().showEvent(event)
        self._restyle()

    def paintEvent(self, event):
        scheme = self._scheme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self._detached or self.isWindow():
            painter.fillRect(rect, scheme.background)
        else:
            # Docked next to other panes, the outline sets it apart from them.
            radius = scaled_px(self, 8)
            painter.setPen(scheme.line)
            painter.setBrush(scheme.background)
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        y = self._header.geometry().bottom() + 1.5
        painter.setPen(scheme.line)
        painter.drawLine(QPointF(rect.left() + 1, y), QPointF(rect.right() - 1, y))
        painter.end()


    def title(self) -> str:
        return self._title.text()

    def set_title(self, text: str):
        self._title.setText(text)

    def set_detachable(self, detachable: bool):
        """Show the button that asks the host for a window of its own (see detachRequested)."""
        self.pop_button.setVisible(bool(detachable))

    def is_detached(self) -> bool:
        return self._detached

    def set_detached(self, detached: bool):
        """Where the host put the panel: in a window of its own or not. The button then offers the way back."""
        self._detached = bool(detached)
        if self._detached:
            self.pop_button.set_icon(POP_IN_SVG, self.tr('Put back in the main window'))
        else:
            self.pop_button.set_icon(POP_OUT_SVG, self.tr('Open in a separate window'))
        self.update()

    def _close(self):
        self.hide()
        self.closeRequested.emit()


    def _new_id(self) -> int:
        item_id = self._next_id
        self._next_id += 1
        return item_id

    def _bubble_limit(self) -> int:
        return max(scaled_px(self, 40), int(self._content.width() * BUBBLE_SHARE))

    def _update_bubble_limits(self):
        limit = self._bubble_limit()
        for bubble in self._bubbles:
            bubble.setMaximumWidth(limit)

    def _avatar(self) -> AssistantIcon:
        icon = AssistantIcon(size=28)
        icon.set_colors(self._scheme.bubble, self._scheme.accent)
        return icon

    def _add_row(self, kind: str, widget: QWidget, bubble: bool = False):
        new_turn = kind != self._last_kind
        # Decided before the new row changes the scroll range: a reader who
        # scrolled up must not be pulled down.
        self._stick_to_bottom = self._is_near_bottom()
        row = _plain(QWidget())
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, scaled_px(self, 6) if new_turn and self._last_kind else 0, 0, 0)
        layout.setSpacing(scaled_px(self, 6))
        if kind == 'user':
            layout.addStretch(1)
            layout.addWidget(widget, 0)
        else:
            if new_turn:
                avatar = self._avatar()
            else:
                avatar = _plain(QWidget())
                avatar.setFixedSize(scaled_px(self, 28), 1)
            layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(widget, 0 if bubble else 1)
            if bubble:
                layout.addStretch(1)
        if bubble:
            widget.setMaximumWidth(self._bubble_limit())
            self._bubbles.append(widget)
        self._last_kind = kind
        self._items_layout.insertWidget(self._items_layout.indexOf(self._busy_row), row)
        self._items.append(row)
        self._place_progress()
        self._fade_in(row)
        self._update_chips()

    def _fade_in(self, widget: QWidget):
        """Fade a new part in; the repeated paints also reach a remote desktop that drops an update now and then."""
        # Hidden, it shows whole when the panel opens. Inside a part still fading in, the effects would nest.
        if not self.isVisible():
            return
        part = widget
        while part is not None and part is not self:
            if part.graphicsEffect() is not None:
                return
            part = part.parentWidget()
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b'opacity', widget)
        fade.setDuration(FADE_IN_MS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        # The effect draws through an off-screen picture: once faded in, the part paints directly again.
        fade.finished.connect(lambda *_: widget.setGraphicsEffect(None))
        fade.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _text(self, text: str, **kwargs) -> _TextView:
        view = _TextView(text, **kwargs)
        view.apply_scheme(self._scheme)
        return view

    def _hint(self) -> _HintLabel:
        label = _HintLabel()
        label.apply_scheme(self._scheme)
        return label

    def _add_message(self, kind: str, text: str) -> int:
        user = kind == 'user'
        if user:
            bubble = _Surface(self._scheme, 'accent', radius=12)
        else:
            bubble = _Surface(self._scheme, 'bubble', 'line', radius=12)
        bubble.setObjectName('chatBubbleUser' if user else 'chatBubbleAssistant')
        inner = QVBoxLayout(bubble)
        pad = scaled_px(self, 8)
        inner.setContentsMargins(pad + 3, pad, pad + 3, pad)
        inner.addWidget(self._text(text, on_accent=user))
        self._add_row(kind, bubble, bubble=True)
        return self._new_id()

    def add_user_message(self, text: str) -> int:
        return self._add_message('user', text)

    def add_assistant_message(self, text: str) -> int:
        return self._add_message('assistant', text)

    def add_card(self, title: str, lines=(), actions=(), options=(), detail: str = '',
                 detail_label: str = 'Details') -> int:
        """A card with a title, plain lines, optional check boxes and buttons.

        ``detail`` (e.g. a formula) is folded behind a ``detail_label`` button.
        """
        card_id = self._new_id()
        frame = _Surface(self._scheme, 'field', 'line', radius=10)
        frame.setObjectName('chatCard')
        card = _Card()
        layout = QVBoxLayout(frame)
        pad = scaled_px(self, 10)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(scaled_px(self, 6))
        layout.addWidget(self._text(title, bold=True))
        for line in lines:
            layout.addWidget(self._text(line))

        options = list(options)
        if options:
            holder = _plain(QWidget())
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(scaled_px(self, 2))
            for key, label, checked in options:
                box = QCheckBox(_literal(label))
                box.setObjectName('chatOption')
                box.setChecked(bool(checked))
                box.setProperty('optionKey', key)
                card.options.append(box)
                holder_layout.addWidget(box)
            if len(options) > MAX_VISIBLE_OPTIONS:
                area = _plain(QScrollArea())
                area.setObjectName('chatOptions')
                area.setWidgetResizable(True)
                area.setFrameShape(QFrame.Shape.NoFrame)
                area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                area.setWidget(holder)
                holder.setAutoFillBackground(False)
                _plain(area.viewport()).setAutoFillBackground(False)
                area.setFixedHeight(MAX_VISIBLE_OPTIONS * (card.options[0].sizeHint().height() + scaled_px(self, 2)))
                layout.addWidget(area)
            else:
                layout.addWidget(holder)

        if detail:
            box = _Surface(self._scheme, 'background', 'line', radius=5)
            box.setObjectName('chatDetail')
            box_layout = QVBoxLayout(box)
            margin = scaled_px(self, 6)
            box_layout.setContentsMargins(margin, margin, margin, margin)
            box_layout.addWidget(self._text(detail, mono=True, object_name='chatDetailText'))
            box.setVisible(False)
            toggle = QToolButton()
            toggle.setObjectName('chatDetailToggle')
            toggle.setText(_literal(detail_label))
            toggle.setCheckable(True)
            toggle.setAutoRaise(True)
            toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            toggle.setArrowType(Qt.ArrowType.RightArrow)

            def unfold(shown, box=box, toggle=toggle):
                box.setVisible(shown)
                toggle.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)

            toggle.toggled.connect(unfold)
            layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(box)

        actions = list(actions)
        if actions:
            holder = _plain(QWidget())
            flow = _FlowLayout(holder, spacing=scaled_px(self, 6))
            for index, (key, label) in enumerate(actions):
                button = QPushButton(_literal(label))
                button.setDefault(index == 0)
                button.setAutoDefault(False)
                button.clicked.connect(lambda *_, k=key: self._on_card_action(card_id, k))
                card.buttons[key] = button
                flow.addWidget(button)
            layout.addWidget(holder)

        card.note = self._hint()
        card.note.setObjectName('chatNote')
        card.note.setWordWrap(True)
        card.note.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        font = _small_font(card.note)
        font.setItalic(True)
        card.note.setFont(font)
        card.note.setVisible(False)
        layout.addWidget(card.note)

        self._cards[card_id] = card
        self._add_row('assistant', frame)
        return card_id

    def _on_card_action(self, card_id: int, key: str):
        card = self._cards.get(card_id)
        if card is None:
            return
        checked = [box.property('optionKey') for box in card.options if box.isChecked()]
        self.cardActionTriggered.emit(card_id, key, checked)

    def set_card_state(self, card_id: int, enabled=None, note=None):
        card = self._cards.get(card_id)
        if card is None:
            return
        if enabled is not None:
            for key, button in card.buttons.items():
                button.setEnabled(key in enabled)
        if note is not None:
            new = bool(note) and note != card.note.text()
            card.note.setText(note)
            card.note.setVisible(bool(note))
            if new:
                self._fade_in(card.note)
        active = any(button.isEnabled() for button in card.buttons.values())
        for box in card.options:
            box.setEnabled(active)

    def clear(self):
        for row in self._items:
            self._items_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._items.clear()
        self._bubbles.clear()
        self._cards.clear()
        self._last_kind = None
        self._last_message = ''
        self._stick_to_bottom = True
        self._place_progress()
        self._update_chips()

    def message_count(self) -> int:
        return len(self._items)


    def _is_near_bottom(self) -> bool:
        bar = self._scroll.verticalScrollBar()
        return bar.maximum() - bar.value() <= scaled_px(self, 40)

    def _on_scrolled(self, value):
        self._stick_to_bottom = self._is_near_bottom()

    def _on_range_changed(self, low, high):
        if self._stick_to_bottom:
            self._scroll.verticalScrollBar().setValue(high)


    def set_busy(self, busy: bool, text: str = ''):
        """The working row with ``text``, while the host works on a message; Stop asks it to stop."""
        busy = bool(busy)
        if busy:
            self._stick_to_bottom = self._is_near_bottom()
        self._busy = busy
        self._busy_label.setText(text if busy else '')
        self._busy_icon.set_active(busy)
        self._busy_row.setVisible(busy)
        self.send_button.setVisible(not busy)
        self.stop_button.setVisible(busy)
        self._update_chips()

    def set_progress(self, text: str):
        """What the host does before it can answer (e.g. starting up); '' hides it.

        Centred while the conversation is empty, else where the next answer will go.
        """
        self._preparing = bool(text)
        self._progress_label.setText(text)
        self._progress_icon.set_active(self._preparing)
        self._progress.setVisible(self._preparing)
        self._place_progress()
        self._update_chips()

    def set_status(self, text: str):
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def set_placeholder(self, text: str):
        self.input.setPlaceholderText(text)

    def set_input_enabled(self, enabled: bool):
        self._input_enabled = bool(enabled)
        self.input.setEnabled(self._input_enabled)
        self.send_button.setEnabled(self._input_enabled)
        self.attach_button.setEnabled(self._input_enabled)
        self._update_chips()

    def set_attachable(self, name_filter: str):
        """Attach files of a name filter ("Tables (*.csv *.xlsx)") by the clip or a drop; '' turns it off."""
        self._attach_filter = name_filter
        self._attach_suffixes = tuple(f'.{s.lower()}' for s in re.findall(r'\*\.(\w+)', name_filter))
        self.attach_button.setVisible(bool(self._attach_suffixes))
        self.setAcceptDrops(bool(self._attach_suffixes))

    def set_attachment(self, text: str):
        """The file the next messages go with, shown above the input box with a button to leave it out; '' hides it."""
        self._attachment_label.setText(text)
        self._attachment_label.setToolTip(text)
        self._attachment.setVisible(bool(text))

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr('Attach a file'), self._attach_dir, self._attach_filter)
        if path:
            self._attach_dir = os.path.dirname(path)
            self.fileAttached.emit(path)

    def _dropped_file(self, mime) -> str:
        if not (self._attach_suffixes and self._input_enabled and mime.hasUrls()):
            return ''
        for url in mime.urls():
            path = url.toLocalFile()
            if path.lower().endswith(self._attach_suffixes) and os.path.isfile(path):
                return path
        return ''

    def dragEnterEvent(self, event):
        if self._dropped_file(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        path = self._dropped_file(event.mimeData())
        if path:
            event.acceptProposedAction()
            self.fileAttached.emit(path)
        else:
            event.ignore()

    def set_suggestions(self, texts, anytime=False):
        """Chips the user can click instead of typing, only while the conversation is empty unless anytime."""
        self._suggestions = list(texts)
        self._suggest_anytime = bool(anytime)
        while self._chips_layout.count():
            old = self._chips_layout.takeAt(0).widget()
            # Gone now, not when the event loop deletes it: it would show under the new ones until then.
            old.hide()
            old.setParent(None)
            old.deleteLater()
        for text in self._suggestions:
            chip = _Chip(text, self._scheme)
            chip.setObjectName('chatChip')
            chip.clicked.connect(lambda *_, t=text: self._emit_message(t))
            self._chips_layout.addWidget(chip)
        self._update_chips()

    def _update_chips(self):
        # Hidden while a click on one could not be sent.
        self._chips.setVisible(bool(self._suggestions) and (self._suggest_anytime or not self._items)
                               and not self._busy and not self._preparing and self._input_enabled)

    def _emit_message(self, text: str):
        if self._busy or not self._input_enabled:
            return
        self._last_message = text
        if self._suggest_anytime:
            self.set_suggestions([])  # next steps answer the last message only
        self.messageSubmitted.emit(text)

    def _submit(self):
        typed = self.input.toPlainText()
        if self._busy or not self._input_enabled:
            return
        if not typed:
            self.emptySubmitted.emit()
            return
        self.input.clear()
        if typed.strip():
            self._emit_message(typed.strip())

    def _recall(self):
        if self._last_message:
            self.input.setPlainText(self._last_message)
            cursor = self.input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.input.setTextCursor(cursor)

    def _on_escape(self):
        if self._busy:
            self.stopRequested.emit()
