import math

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontDatabase, QPainter, QPalette, QTextOption
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLayout, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from iplotWidgets.chatPanel.assistantIcon import AssistantIcon
from iplotWidgets.sizing import scaled_px

#: Share of the conversation width a bubble may take.
BUBBLE_SHARE = 0.85
#: Options beyond this many get a scroll area instead of growing the card.
MAX_VISIBLE_OPTIONS = 8
MAX_INPUT_LINES = 5

_ROLE = QPalette.ColorRole


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
            # A single entry wider than the panel is cut instead of widening it.
            width = min(hint.width(), max(area.width(), 1))
            if x > area.x() and x + width > area.right() + 1:
                x = area.x()
                y += row_height + self._gap
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), QSize(width, hint.height())))
            x += width + self._gap
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + m.bottom()


class _TextView(QTextEdit):
    """Read-only, selectable plain text that wraps anywhere and sizes itself to its content.

    A ``QLabel`` only breaks at word boundaries, so a long variable name would widen the panel.
    """

    def __init__(self, text: str, parent=None, bold: bool = False, mono: bool = False, object_name='chatText'):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if mono:
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            if self.font().pointSizeF() > 0:
                font.setPointSizeF(self.font().pointSizeF())
            self.setFont(font)
        if bold:
            font = self.font()
            font.setBold(True)
            self.setFont(font)
        self._text = text
        self.setPlainText(text)
        self.setFixedHeight(self._height_for(scaled_px(self, 200)))

    def _height_for(self, width: int) -> int:
        doc = self.document()
        doc.setTextWidth(max(width, 1))
        return int(math.ceil(doc.size().height()))

    def natural_width(self) -> int:
        metrics = self.fontMetrics()
        return max((metrics.horizontalAdvance(line) for line in self._text.split('\n')), default=0) + 4

    def sizeHint(self):
        return QSize(self.natural_width(), self.height())

    def minimumSizeHint(self):
        return QSize(scaled_px(self, 24), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        height = self._height_for(self.viewport().width())
        if height != self.height():
            self.setFixedHeight(height)

    def wheelEvent(self, event):
        # Nothing to scroll here; let the conversation scroll instead.
        event.ignore()


class _InputEdit(QPlainTextEdit):
    submitRequested = Signal()
    recallRequested = Signal()
    escapePressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._fit_height())
        self._fit_height()

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
        if event.type() == QEvent.Type.FontChange:
            self._fit_height()

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
    """A rounded panel painted from palette roles, so it follows any theme.

    A stylesheet on a widget whose palette the host set would reset that palette.
    """

    def __init__(self, fill, border=None, radius=10, inverted=False, parent=None):
        super().__init__(parent)
        self._fill = fill
        self._border = border
        self._radius = radius
        self._inverted = inverted

    def paintEvent(self, event):
        palette = self.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._border is None:
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setPen(palette.color(self._border))
        painter.setBrush(palette.color(self._fill))
        radius = scaled_px(self, self._radius)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.end()

    def restyle_children(self):
        # Text on the highlight colour swaps the highlight roles with the
        # normal ones, selection included, or a selection would vanish.
        if not self._inverted:
            return
        base = self.palette()
        for view in self.findChildren(_TextView):
            palette = QPalette(base)
            palette.setColor(_ROLE.Text, base.color(_ROLE.HighlightedText))
            palette.setColor(_ROLE.Highlight, base.color(_ROLE.HighlightedText))
            palette.setColor(_ROLE.HighlightedText, base.color(self._fill))
            view.setPalette(palette)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self.restyle_children()


class _HintLabel(QLabel):
    """A label in the low-contrast placeholder colour."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Status and notes carry error messages; QLabel would guess rich text from a '<'.
        self.setTextFormat(Qt.TextFormat.PlainText)

    def _follow_palette(self):
        palette = self.palette()
        hint = palette.color(_ROLE.PlaceholderText)
        if palette.color(_ROLE.WindowText) != hint:
            palette.setColor(_ROLE.WindowText, hint)
            self.setPalette(palette)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._follow_palette()

    def showEvent(self, event):
        super().showEvent(event)
        self._follow_palette()


class _Chip(QPushButton):
    """A flat suggestion button with a rounded outline."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.text()) + 2 * scaled_px(self, 10),
                     metrics.height() + 2 * scaled_px(self, 4) + 2)

    def minimumSizeHint(self):
        return QSize(scaled_px(self, 24), self.sizeHint().height())

    def paintEvent(self, event):
        palette = self.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(palette.color(_ROLE.AlternateBase) if self.underMouse() else Qt.BrushStyle.NoBrush)
        painter.setPen(palette.color(_ROLE.Highlight if self.hasFocus() else _ROLE.Mid))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(palette.color(_ROLE.Text))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                             self.width() - 2 * scaled_px(self, 10))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


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
    """A conversation view with an input line. It knows nothing about who answers."""

    messageSubmitted = Signal(str)
    cardActionTriggered = Signal(int, str, list)
    stopRequested = Signal()
    # Enter with nothing typed: the host may take it as "yes" to what is on screen (e.g. Apply).
    emptySubmitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._next_id = 1
        self._items = []
        self._bubbles = []
        self._cards = {}
        self._last_kind = None
        self._busy = False
        self._input_enabled = True
        self._last_message = ''
        self._stick_to_bottom = True
        self._suggestions = []
        self._suggest_anytime = False

        self.setMinimumWidth(scaled_px(self, 280))
        gap = scaled_px(self, 6)

        self._content = _Conversation()
        self._content.setObjectName('chatContent')
        self._items_layout = QVBoxLayout(self._content)
        self._items_layout.setContentsMargins(gap, gap, gap, gap)
        self._items_layout.setSpacing(gap)
        self._busy_row = self._build_busy_row()
        self._items_layout.addWidget(self._busy_row)
        self._items_layout.addStretch(1)
        self._content.resized.connect(self._update_bubble_limits)

        self._scroll = QScrollArea()
        self._scroll.setObjectName('chatScroll')
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._content)
        # setWidget turns autofill on; the viewport already paints the Base colour.
        self._content.setAutoFillBackground(False)
        self._scroll.viewport().setBackgroundRole(_ROLE.Base)
        self._scroll.viewport().setAutoFillBackground(True)
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(self._on_range_changed)
        bar.valueChanged.connect(self._on_scrolled)

        self._chips = QWidget()
        self._chips.setObjectName('chatChips')
        self._chips_layout = _FlowLayout(self._chips, spacing=gap)
        self._chips.setVisible(False)

        self.input = _InputEdit()
        self.input.setObjectName('chatInput')
        self.input.submitRequested.connect(self._submit)
        self.input.recallRequested.connect(self._recall)
        self.input.escapePressed.connect(self._on_escape)
        self.send_button = QPushButton(self.tr('Send'))
        self.send_button.setObjectName('chatSend')
        self.send_button.clicked.connect(lambda *_: self._submit())
        self.stop_button = QPushButton(self.tr('Stop'))
        self.stop_button.setObjectName('chatStop')
        self.stop_button.clicked.connect(lambda *_: self.stopRequested.emit())
        self.stop_button.setVisible(False)

        input_row = QHBoxLayout()
        input_row.setSpacing(gap)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        input_row.addWidget(self.stop_button, 0, Qt.AlignmentFlag.AlignBottom)

        self._status = _HintLabel()
        self._status.setObjectName('chatStatus')
        self._status.setFont(_small_font(self._status))
        self._status.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setSpacing(gap)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._chips)
        layout.addLayout(input_row)
        layout.addWidget(self._status)

    def _build_busy_row(self):
        row = QWidget()
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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.setMinimumWidth(scaled_px(self, 280))


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

    def _add_row(self, kind: str, widget: QWidget, bubble: bool = False):
        new_turn = kind != self._last_kind
        # Decided before the new row changes the scroll range: a reader who
        # scrolled up must not be pulled down.
        self._stick_to_bottom = self._is_near_bottom()
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, scaled_px(self, 6) if new_turn and self._last_kind else 0, 0, 0)
        layout.setSpacing(scaled_px(self, 6))
        if kind == 'user':
            layout.addStretch(1)
            layout.addWidget(widget, 0)
        else:
            if new_turn:
                avatar = AssistantIcon(size=28)
            else:
                avatar = QWidget()
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
        self._update_chips()

    def _add_message(self, kind: str, text: str) -> int:
        user = kind == 'user'
        if user:
            bubble = _Surface(_ROLE.Highlight, radius=10, inverted=True)
        else:
            bubble = _Surface(_ROLE.AlternateBase, _ROLE.Mid, radius=10)
        bubble.setObjectName('chatBubbleUser' if user else 'chatBubbleAssistant')
        inner = QVBoxLayout(bubble)
        pad = scaled_px(self, 8)
        inner.setContentsMargins(pad + 2, pad, pad + 2, pad)
        inner.addWidget(_TextView(text))
        bubble.restyle_children()
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
        frame = _Surface(_ROLE.Window, _ROLE.Mid, radius=10)
        frame.setObjectName('chatCard')
        card = _Card()
        layout = QVBoxLayout(frame)
        pad = scaled_px(self, 10)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(scaled_px(self, 6))
        layout.addWidget(_TextView(title, bold=True))
        for line in lines:
            layout.addWidget(_TextView(line))

        options = list(options)
        if options:
            holder = QWidget()
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(scaled_px(self, 2))
            for key, label, checked in options:
                box = QCheckBox(_literal(label))
                box.setChecked(bool(checked))
                box.setProperty('optionKey', key)
                card.options.append(box)
                holder_layout.addWidget(box)
            if len(options) > MAX_VISIBLE_OPTIONS:
                area = QScrollArea()
                area.setObjectName('chatOptions')
                area.setWidgetResizable(True)
                area.setFrameShape(QFrame.Shape.NoFrame)
                area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                area.setWidget(holder)
                holder.setAutoFillBackground(False)
                area.viewport().setAutoFillBackground(False)
                area.setFixedHeight(MAX_VISIBLE_OPTIONS * (card.options[0].sizeHint().height() + scaled_px(self, 2)))
                layout.addWidget(area)
            else:
                layout.addWidget(holder)

        if detail:
            box = _Surface(_ROLE.Base, _ROLE.Midlight, radius=5)
            box.setObjectName('chatDetail')
            box_layout = QVBoxLayout(box)
            margin = scaled_px(self, 6)
            box_layout.setContentsMargins(margin, margin, margin, margin)
            box_layout.addWidget(_TextView(detail, mono=True, object_name='chatDetailText'))
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
            holder = QWidget()
            flow = _FlowLayout(holder, spacing=scaled_px(self, 6))
            for index, (key, label) in enumerate(actions):
                button = QPushButton(_literal(label))
                button.setDefault(index == 0)
                button.setAutoDefault(False)
                button.clicked.connect(lambda *_, k=key: self._on_card_action(card_id, k))
                card.buttons[key] = button
                flow.addWidget(button)
            layout.addWidget(holder)

        card.note = _HintLabel()
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
            card.note.setText(note)
            card.note.setVisible(bool(note))
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

    def set_status(self, text: str):
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def set_placeholder(self, text: str):
        self.input.setPlaceholderText(text)

    def set_input_enabled(self, enabled: bool):
        self._input_enabled = bool(enabled)
        self.input.setEnabled(self._input_enabled)
        self.send_button.setEnabled(self._input_enabled)
        self._update_chips()

    def set_suggestions(self, texts, anytime=False):
        """Chips the user can click instead of typing, only while the conversation is empty unless anytime."""
        self._suggestions = list(texts)
        self._suggest_anytime = bool(anytime)
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            item.widget().deleteLater()
        for text in self._suggestions:
            chip = _Chip(text)
            chip.setObjectName('chatChip')
            chip.clicked.connect(lambda *_, t=text: self._emit_message(t))
            self._chips_layout.addWidget(chip)
        self._update_chips()

    def _update_chips(self):
        # Hidden while a click on one could not be sent.
        self._chips.setVisible(bool(self._suggestions) and (self._suggest_anytime or not self._items)
                               and not self._busy and self._input_enabled)

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
