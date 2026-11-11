# Description: Unit tests for ChatPanel and AssistantIcon.

import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QTextEdit, QToolButton, QWidget

from iplotWidgets.chatPanel import AssistantIcon, ChatPanel, assistant_icon
from iplotWidgets.chatPanel import assistantIcon as icon_module
from iplotWidgets.chatPanel.chatPanel import FADE_IN_MS


@pytest.fixture
def panel(qapp):
    widget = ChatPanel()
    widget.resize(380, 560)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


class Recorder:
    def __init__(self, signal):
        self.calls = []
        signal.connect(lambda *args: self.calls.append(args))


def _texts(panel):
    return [view.toPlainText() for view in panel.findChildren(QTextEdit)]


def _button(panel, card_id, key):
    return panel._cards[card_id].buttons[key]


class TestSubmit:

    def test_send_button_emits_stripped_text_and_clears(self, panel):
        rec = Recorder(panel.messageSubmitted)
        panel.input.setPlainText('  hello  ')
        panel.send_button.click()
        assert rec.calls == [('hello',)]
        assert panel.input.toPlainText() == ''

    def test_enter_submits(self, panel):
        rec = Recorder(panel.messageSubmitted)
        panel.input.setPlainText('plot it\n')
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert rec.calls == [('plot it',)]
        assert panel.input.toPlainText() == ''

    def test_shift_enter_inserts_newline(self, panel):
        rec = Recorder(panel.messageSubmitted)
        panel.input.setPlainText('a')
        panel.input.moveCursor(panel.input.textCursor().MoveOperation.End)
        QTest.keyClick(panel.input, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        assert rec.calls == []
        assert panel.input.toPlainText() == 'a\n'

    @pytest.mark.parametrize('text', ['', '   ', '\n \t\n'])
    def test_blank_text_does_not_emit(self, panel, text):
        rec = Recorder(panel.messageSubmitted)
        panel.input.setPlainText(text)
        panel.send_button.click()
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert rec.calls == []

    def test_up_recalls_last_message_only_when_empty(self, panel):
        panel.input.setPlainText('first')
        panel.send_button.click()
        panel.input.setPlainText('second')
        panel.send_button.click()
        QTest.keyClick(panel.input, Qt.Key.Key_Up)
        assert panel.input.toPlainText() == 'second'
        panel.input.setPlainText('typed')
        QTest.keyClick(panel.input, Qt.Key.Key_Up)
        assert panel.input.toPlainText() == 'typed'

    def test_input_grows_to_five_lines_at_most(self, panel, qapp):
        one = panel.input.height()
        panel.input.setPlainText('\n'.join('x' * 3 for _ in range(3)))
        qapp.processEvents()
        three = panel.input.height()
        panel.input.setPlainText('\n'.join('x' * 3 for _ in range(30)))
        qapp.processEvents()
        assert one < three < panel.input.height()
        five_lines = panel.input.height()
        panel.input.setPlainText('\n'.join('x' * 3 for _ in range(60)))
        qapp.processEvents()
        assert panel.input.height() == five_lines

    def test_input_disabled_blocks_send(self, panel):
        rec = Recorder(panel.messageSubmitted)
        panel.input.setPlainText('hello')
        panel.set_input_enabled(False)
        assert not panel.send_button.isEnabled()
        panel._submit()
        assert rec.calls == []


class TestBusy:

    def test_busy_blocks_submit_and_shows_stop(self, panel):
        rec = Recorder(panel.messageSubmitted)
        panel.set_busy(True, 'Thinking')
        assert panel.stop_button.isVisible() and not panel.send_button.isVisible()
        assert panel._busy_row.isVisible()
        panel.input.setPlainText('next')
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert rec.calls == []
        assert panel.input.toPlainText() == 'next'
        panel.set_busy(False)
        assert panel.send_button.isVisible() and not panel.stop_button.isVisible()
        assert not panel._busy_row.isVisible()
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert rec.calls == [('next',)]

    def test_stop_button_and_escape_emit_stop(self, panel):
        rec = Recorder(panel.stopRequested)
        panel.set_busy(True, 'Thinking')
        panel.stop_button.click()
        QTest.keyClick(panel.input, Qt.Key.Key_Escape)
        assert len(rec.calls) == 2

    def test_progress_shows_in_the_middle_of_an_empty_conversation_and_offers_no_stop(self, panel, qapp):
        rec = Recorder(panel.stopRequested)
        panel.set_suggestions(['Hello'])
        panel.set_progress('Loading the model…')
        qapp.processEvents()
        assert panel._progress.isVisible() and panel._progress_label.text() == 'Loading the model…'
        assert panel._progress_icon.is_animating()
        assert not panel._busy_row.isVisible()
        viewport = panel._scroll.viewport()
        middle = panel._progress.mapTo(viewport, panel._progress.rect().center()).y()
        assert abs(middle - viewport.height() / 2) <= viewport.height() * 0.05
        assert not panel._chips.isVisible()
        assert panel.stop_button.isHidden() and not panel.send_button.isHidden()
        QTest.keyClick(panel.input, Qt.Key.Key_Escape)
        assert rec.calls == []
        panel.set_progress('')
        assert not panel._progress.isVisible() and not panel._progress_icon.is_animating()
        assert panel._chips.isVisible(), 'then the suggestions'

    def test_progress_after_messages_goes_where_the_next_answer_will(self, panel, qapp):
        panel.add_assistant_message('The assistant stopped. Send a message and it starts again.')
        panel.set_progress('Waking up the assistant…')
        qapp.processEvents()
        assert panel._progress.geometry().top() > panel._items[-1].geometry().bottom()
        assert panel._items[0].geometry().top() < panel._scroll.viewport().height() / 4, 'messages stay on top'

    def test_escape_when_idle_does_nothing(self, panel):
        rec = Recorder(panel.stopRequested)
        QTest.keyClick(panel.input, Qt.Key.Key_Escape)
        assert rec.calls == []


class TestCard:

    def _card(self, panel, **kwargs):
        return panel.add_card('Title', ['one', 'two'],
                              actions=[('apply', 'Apply'), ('undo', 'Undo')],
                              options=[('a', 'A', True), ('b', 'B', True), ('c', 'C', False)],
                              detail='x = 1', **kwargs)

    def test_action_reports_checked_options(self, panel):
        rec = Recorder(panel.cardActionTriggered)
        card_id = self._card(panel)
        panel._cards[card_id].options[1].setChecked(False)
        _button(panel, card_id, 'apply').click()
        assert rec.calls == [(card_id, 'apply', ['a'])]

    def test_card_without_options_reports_empty_list(self, panel):
        rec = Recorder(panel.cardActionTriggered)
        card_id = panel.add_card('T', actions=[('ok', 'OK')])
        _button(panel, card_id, 'ok').click()
        assert rec.calls == [(card_id, 'ok', [])]

    def test_first_action_is_default(self, panel):
        card_id = self._card(panel)
        assert _button(panel, card_id, 'apply').isDefault()
        assert not _button(panel, card_id, 'undo').isDefault()

    def test_set_card_state(self, panel, qapp):
        card_id = self._card(panel)
        card = panel._cards[card_id]
        panel.set_card_state(card_id, enabled=['undo'], note='Applied')
        qapp.processEvents()
        assert not _button(panel, card_id, 'apply').isEnabled()
        assert _button(panel, card_id, 'undo').isEnabled()
        assert card.note.text() == 'Applied' and card.note.isVisible()
        assert all(box.isEnabled() for box in card.options)
        panel.set_card_state(card_id, enabled=[], note='Done')
        qapp.processEvents()
        assert card.note.text() == 'Done'
        assert not any(box.isEnabled() for box in card.options), 'no button left to use them'
        panel.set_card_state(card_id, note='')
        qapp.processEvents()
        assert not card.note.isVisible()

    def test_ampersands_are_shown_not_taken_for_shortcuts(self, panel):
        card_id = panel.add_card('T', actions=[('a', 'Add & draw')], options=[('k', 'A&B', False)],
                                 detail='x', detail_label='Inputs & formula')
        card = panel._cards[card_id]
        assert card.options[0].text() == 'A&&B'
        assert _button(panel, card_id, 'a').text() == 'Add && draw'
        assert panel.findChild(QToolButton, 'chatDetailToggle').text() == 'Inputs && formula'

    def test_unknown_card_is_ignored(self, panel):
        panel.set_card_state(999, enabled=[], note='x')

    def test_many_options_scroll(self, panel):
        options = [(str(i), 'opt %d' % i, False) for i in range(20)]
        card_id = panel.add_card('T', options=options, actions=[('ok', 'OK')])
        area = panel._cards[card_id].options[0].parent().parent().parent()
        assert area.objectName() == 'chatOptions'
        assert area.height() < 20 * panel._cards[card_id].options[0].sizeHint().height()

    def test_detail_is_monospace_and_selectable(self, panel):
        self._card(panel)
        detail = [v for v in panel.findChildren(QTextEdit) if v.objectName() == 'chatDetailText'][0]
        assert detail.toPlainText() == 'x = 1'
        assert detail.font().family() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        assert detail.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse

    def test_detail_is_folded_until_asked_for(self, panel, qapp):
        panel.show()
        self._card(panel, detail_label='Formula')
        qapp.processEvents()
        box = panel.findChild(QWidget, 'chatDetail')
        toggle = panel.findChild(QToolButton, 'chatDetailToggle')
        assert toggle.text() == 'Formula'
        assert toggle.isVisible() and not box.isVisible()
        toggle.click()
        assert box.isVisible()
        assert toggle.arrowType() == Qt.ArrowType.DownArrow
        toggle.click()
        assert not box.isVisible()


class TestSuggestions:

    def test_chip_emits_and_hides_after_first_message(self, panel, qapp):
        rec = Recorder(panel.messageSubmitted)
        panel.set_suggestions(['Plot the density', 'Add a ruler'])
        qapp.processEvents()
        assert panel._chips.isVisible()
        chips = panel._chips.findChildren(QPushButton)
        assert [c.text() for c in chips] == ['Plot the density', 'Add a ruler']
        chips[1].click()
        assert rec.calls == [('Add a ruler',)]
        panel.add_user_message('Add a ruler')
        assert not panel._chips.isVisible()
        panel.clear()
        assert panel._chips.isVisible()

    def test_next_steps_show_after_messages_until_used(self, panel, qapp):
        rec = Recorder(panel.messageSubmitted)
        panel.add_user_message('smooth it')
        panel.set_suggestions(['The same for VAR2'], anytime=True)
        qapp.processEvents()
        assert panel._chips.isVisible()
        panel._chips.findChildren(QPushButton)[0].click()
        assert rec.calls == [('The same for VAR2',)]
        assert not panel._chips.isVisible(), 'they answered the last message only'
        panel.set_suggestions(['Derivative of it'], anytime=True)
        panel.input.setPlainText('something else')
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert not panel._chips.isVisible()

    def test_enter_with_nothing_typed_says_so(self, panel):
        empty = Recorder(panel.emptySubmitted)
        sent = Recorder(panel.messageSubmitted)
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert len(empty.calls) == 1 and sent.calls == []
        panel.set_busy(True)
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert len(empty.calls) == 1, 'not while busy'

    @pytest.mark.parametrize('text', ['   ', '\n \t\n'])
    def test_blank_text_is_cleared_not_taken_for_an_empty_enter(self, panel, text):
        empty = Recorder(panel.emptySubmitted)
        panel.input.setPlainText(text)
        QTest.keyClick(panel.input, Qt.Key.Key_Return)
        assert empty.calls == []
        assert panel.input.toPlainText() == ''

    def test_new_suggestions_replace_the_old_ones_at_once(self, panel, qapp):
        panel.set_suggestions(['Smooth MLT1000-AA-IN over 10 s'])
        qapp.processEvents()
        panel.add_user_message('Smooth MLT1000-AA-IN over 10 s')
        panel.set_suggestions(['The same for VOL3600-XI'], anytime=True)
        shown = [c.text() for c in panel._chips.findChildren(QPushButton) if c.isVisibleTo(panel)]
        assert shown == ['The same for VOL3600-XI'], 'the old one would show under it until deleted'

    def test_chips_hide_while_a_click_could_not_be_sent(self, panel, qapp):
        panel.set_suggestions(['Add a ruler'])
        qapp.processEvents()
        panel.set_busy(True)
        assert not panel._chips.isVisible()
        panel.set_busy(False)
        assert panel._chips.isVisible()
        panel.set_input_enabled(False)
        assert not panel._chips.isVisible()

    def test_chips_wrap_without_widening(self, panel, qapp):
        panel.resize(320, 560)
        panel.set_suggestions(['a fairly long suggestion %d' % i for i in range(8)])
        qapp.processEvents()
        assert panel._chips.width() <= panel.width()
        assert panel._chips.height() > panel._chips.findChildren(QPushButton)[0].height()

    def test_a_chip_wider_than_the_panel_wraps_its_text_instead_of_cutting_it(self, panel, qapp):
        from iplotWidgets.chatPanel.chatPanel import _wrapped_height
        panel.resize(300, 560)
        long = 'The same for CRYO-CH-MM-CRST:MLT1000-AA-IN and CRYO-CH-CB3-HESC:VOL3600-XI'
        panel.set_suggestions([long, 'Log scale on the top plot'])
        qapp.processEvents()
        chip, short = panel._chips.findChildren(QPushButton)
        assert chip.width() <= panel._chips.width()
        assert chip.height() > short.height(), 'grown down to more lines'
        across, down = chip._padding()
        assert _wrapped_height(long, chip.font(), chip.width() - 2 * across) <= chip.height() - 2 * down
        assert chip.geometry().bottom() < short.geometry().top()

    def test_a_chip_holds_its_text_on_one_line_with_room_to_spare(self, panel, qapp):
        from iplotWidgets.chatPanel.chatPanel import _wrapped_height
        panel.resize(900, 560)
        panel.set_suggestions(['Log scale on the top plot', 'Smooth MLT1000-AA-IN over 10 s'])
        qapp.processEvents()
        for chip in panel._chips.findChildren(QPushButton):
            across, down = chip._padding()
            one_line = chip.sizeHint().height() - 2 * down
            # At its own width, and a pixel narrower (a fractional screen scale rounds the other way).
            for width in (chip.width(), chip.width() - 1):
                assert _wrapped_height(chip.text(), chip.font(), width - 2 * across) <= one_line, chip.text()


class TestMessage:

    def test_html_is_shown_literally(self, panel):
        panel.add_user_message('<b>x</b>')
        panel.add_assistant_message('<i>y</i> &amp; z')
        assert '<b>x</b>' in _texts(panel)
        assert '<i>y</i> &amp; z' in _texts(panel)

    def test_ids_are_unique_and_counted(self, panel):
        ids = [panel.add_user_message('a'), panel.add_assistant_message('b'), panel.add_card('c')]
        assert len(set(ids)) == 3
        assert panel.message_count() == 3
        panel.clear()
        assert panel.message_count() == 0

    def test_long_token_does_not_widen_panel(self, panel, qapp):
        panel.resize(320, 560)
        qapp.processEvents()
        token = 'v' * 120
        panel.add_assistant_message(token)
        panel.add_user_message(token)
        panel.add_card('T ' + token, [token], detail=token)
        qapp.processEvents()
        panel.findChild(QToolButton, 'chatDetailToggle').click()  # the formula, unfolded, must fit too
        qapp.processEvents()
        qapp.processEvents()
        viewport = panel._scroll.viewport()
        assert panel._content.width() <= viewport.width()
        assert not panel._scroll.horizontalScrollBar().isVisible()
        assert panel.width() == 320
        for view in panel.findChildren(QTextEdit):
            if view is not panel.input:
                assert view.width() <= viewport.width()

    def test_bubble_width_limited(self, panel, qapp):
        panel.add_user_message('word ' * 100)
        qapp.processEvents()
        bubble = panel._bubbles[0]
        assert bubble.width() <= panel._content.width() * 0.85 + 1

    def test_autoscroll_only_when_at_bottom(self, panel, qapp):
        for i in range(30):
            panel.add_assistant_message('line %d\nsecond line' % i)
        qapp.processEvents()
        qapp.processEvents()
        bar = panel._scroll.verticalScrollBar()
        assert bar.maximum() > 0 and bar.value() == bar.maximum()
        bar.setValue(0)
        panel.add_assistant_message('new')
        qapp.processEvents()
        assert bar.value() == 0
        bar.setValue(bar.maximum())
        panel.add_assistant_message('newer')
        qapp.processEvents()
        assert bar.value() == bar.maximum()

    def test_status_and_placeholder(self, panel):
        panel.set_status('Model ready')
        assert panel._status.isVisible() and panel._status.text() == 'Model ready'
        panel.set_status('')
        assert not panel._status.isVisible()
        panel.set_placeholder('Ask')
        assert panel.input.placeholderText() == 'Ask'

    def test_many_messages_are_fast(self, panel, qapp):
        start = time.perf_counter()
        for i in range(200):
            panel.add_user_message('message %d' % i) if i % 2 else panel.add_assistant_message('answer %d' % i)
        qapp.processEvents()
        assert time.perf_counter() - start < 3.0
        assert panel.message_count() == 200

    def test_palette_change_recolours_bubbles(self, panel, qapp):
        panel.add_user_message('hi')
        qapp.processEvents()
        bubble = panel._bubbles[0]
        probe = (4, bubble.height() // 2)
        before = bubble.grab().toImage().pixelColor(*probe)
        palette = QPalette(panel.palette())
        palette.setColor(QPalette.ColorRole.Highlight, QColor('#ff0000'))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#00ff00'))
        panel.setPalette(palette)
        qapp.processEvents()
        after = bubble.grab().toImage().pixelColor(*probe)
        assert before != after and after.name() == '#ff0000'
        view = bubble.findChildren(QTextEdit)[0]
        assert view.palette().color(QPalette.ColorRole.Text).name() == '#00ff00'


@pytest.fixture
def host_style(qapp):
    """Sets an application style sheet for the test and takes it away after."""
    def apply(sheet):
        qapp.setStyleSheet(sheet)
        qapp.processEvents()
    yield apply
    qapp.setStyleSheet('')


class TestHostStyle:

    def test_messages_fit_under_a_host_style_sheet_with_padding(self, panel, qapp, host_style):
        # A host style sheet that frames and pads every text edit must not cut the last line.
        host_style('QTextEdit, QPlainTextEdit { border: 1px solid #888; padding: 4px 6px; }')
        panel.add_assistant_message('I can smooth or filter signals, combine them, change the plots, add variables '
                                    'and set the time range. What do you need?')
        panel.add_card('Title', ['a line of the card'])
        for _ in range(3):
            qapp.processEvents()
        for view in panel.findChildren(QTextEdit):
            document = view.document()
            document.setTextWidth(view.viewport().width())
            assert view.viewport().height() >= document.size().height() - 0.5, view.toPlainText()

    def test_an_answer_is_laid_out_right_at_first_paint(self, qapp, host_style):
        # An answer and its card arrive at once; it must look right before any click relays it out.
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QLabel, QSplitter
        from iplotWidgets.chatPanel.chatPanel import _Surface
        host_style('QTextEdit, QPlainTextEdit { border: 1px solid #888; padding: 2px 4px; }')
        splitter = QSplitter()
        splitter.addWidget(QLabel('canvas'))
        panel = ChatPanel()
        splitter.addWidget(panel)
        splitter.resize(800, 700)
        splitter.setSizes([440, 360])
        splitter.show()
        qapp.processEvents()
        splitter.setFont(QFont(splitter.font().family(), 13))  # the host scales its fonts after building
        qapp.processEvents()
        panel.add_user_message('Smooth MLT1000-AA-IN over 10 s')
        panel.add_assistant_message("Here's what I'd change. Nothing happens until you click Apply, and Undo puts "
                                    "it back.")
        panel.add_card('Smoothing', ['CRYO-CH-MM-CRST:MLT1000-AA-IN, smoothed with a 10 s average, in the top plot'],
                       [('apply', 'Apply'), ('undo', 'Undo')], detail='uniform_filter1d(x, 3)')
        qapp.processEvents()
        for surface in panel.findChildren(_Surface):
            for child in surface.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
                if child.isVisibleTo(surface):
                    assert child.geometry().bottom() < surface.height(), surface.objectName()
        rows = panel._items
        assert all(a.geometry().bottom() < b.geometry().top() for a, b in zip(rows, rows[1:]))
        splitter.deleteLater()

    def test_colours_follow_a_dark_theme_set_only_by_style_sheet(self, panel, qapp, host_style):
        # A theme style sheet sets window and text colours, not Base: the panel must not stay white.
        host_style('QWidget { background-color: #2b2d31; color: #e6e8eb; }')
        panel.add_assistant_message('hello')
        qapp.processEvents()
        assert panel._scheme.background.lightnessF() < 0.3
        assert panel._scheme.text.name() == '#e6e8eb'
        image = panel.grab().toImage()
        assert image.pixelColor(panel.width() // 2, panel.height() // 2).lightnessF() < 0.3


def _wait(predicate, timeout=2.0):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        QTest.qWait(20)
    return predicate()


def _faded_in(widgets):
    return all(widget.graphicsEffect() is None for widget in widgets)


class TestFadeIn:

    def test_a_new_message_or_card_fades_in_then_paints_directly(self, panel):
        panel.add_user_message('smooth it')
        panel.add_card('Smoothing', ['a line'], [('apply', 'Apply')])
        for row in panel._items:
            effect = row.graphicsEffect()
            assert isinstance(effect, QGraphicsOpacityEffect) and effect.opacity() == 0.0, 'starts unseen'
        assert _wait(lambda: _faded_in(panel._items))

    def test_a_hidden_panel_shows_new_parts_whole(self, qapp):
        panel = ChatPanel()
        panel.add_assistant_message('hello')
        panel.add_card('Smoothing', ['a line'], [('apply', 'Apply')])
        assert _faded_in(panel._items)
        panel.deleteLater()

    def test_a_note_fades_in_when_it_says_something_new(self, panel):
        card = panel.add_card('Smoothing', ['a line'], [('apply', 'Apply'), ('undo', 'Undo')])
        assert _wait(lambda: _faded_in(panel._items))
        note = panel._cards[card].note
        panel.set_card_state(card, enabled=['undo'], note='Done.')
        assert isinstance(note.graphicsEffect(), QGraphicsOpacityEffect)
        assert _wait(lambda: _faded_in([note]))
        panel.set_card_state(card, enabled=['undo'], note='Done.')
        assert note.graphicsEffect() is None, 'the same words are not new'
        panel.set_card_state(card, enabled=['apply'], note='')
        assert note.graphicsEffect() is None and not note.isVisible()

    def test_a_note_inside_a_card_still_fading_in_fades_with_it(self, panel):
        card = panel.add_card('Smoothing', ['a line'], [('apply', 'Apply')])
        panel.set_card_state(card, note='Tick at least one.')
        assert panel._cards[card].note.graphicsEffect() is None, 'effects inside effects are drawn twice'
        assert _wait(lambda: _faded_in(panel._items))

    def test_clearing_while_fading_in_is_quiet(self, panel, monkeypatch):
        errors = []
        monkeypatch.setattr('sys.excepthook', lambda *args: errors.append(args))
        panel.add_assistant_message('hello')
        panel.clear()
        QTest.qWait(FADE_IN_MS + 150)
        assert errors == [] and panel.message_count() == 0


class TestWindow:

    def test_the_title_has_the_assistant_mark_in_the_text_colour(self, panel, host_style):
        icon = panel._title_icon
        assert icon.isVisible() and icon.geometry().right() < panel._title.geometry().left()
        dark = icon.pixmap().toImage()
        host_style('QWidget { background-color: #2b2d31; color: #e6e8eb; }')
        light = icon.pixmap().toImage()
        assert dark != light, 'redrawn with the theme'

    def test_title_and_close(self, panel):
        closed = Recorder(panel.closeRequested)
        assert panel.title() == 'Assistant'
        panel.set_title('Helper')
        assert panel._title.text() == 'Helper'
        panel.close_button.click()
        assert not panel.isVisible() and len(closed.calls) == 1

    def test_the_window_button_asks_the_host_and_offers_the_way_back(self, panel):
        assert not panel.pop_button.isVisible(), 'only when the host can move the panel'
        panel.set_detachable(True)
        assert panel.pop_button.isVisible()
        asked = Recorder(panel.detachRequested)
        panel.pop_button.click()
        assert asked.calls == [(True,)] and not panel.is_detached(), 'the host moves it'
        panel.set_detached(True)
        assert 'main window' in panel.pop_button.toolTip()
        panel.pop_button.click()
        assert asked.calls == [(True,), (False,)]
        panel.set_detached(False)
        assert 'separate window' in panel.pop_button.toolTip()


class TestAssistantIcon:

    def test_animation_runs_only_while_active_and_visible(self, qapp):
        icon = AssistantIcon()
        icon.show()
        qapp.processEvents()
        assert not icon.is_animating()
        icon.set_active(True)
        assert icon.is_animating()
        icon.hide()
        assert not icon.is_animating()
        icon.show()
        assert icon.is_animating()
        icon.set_active(False)
        assert not icon.is_animating()
        icon.deleteLater()
        closed = QWidget()
        inside = AssistantIcon(closed)
        inside.set_active(True)
        assert not inside.is_animating(), 'inside a panel that is not shown'
        closed.show()
        qapp.processEvents()
        assert inside.is_animating()
        closed.deleteLater()

    def test_svg_is_parsed_once_per_colour(self, qapp):
        icon_module._cached_renderer.cache_clear()
        icon = AssistantIcon()
        icon.show()
        icon.set_active(True)
        for _ in range(5):
            icon.grab()
        # the two stars: two renderers, whatever the number of frames
        assert icon_module._cached_renderer.cache_info().currsize == 2
        icon.deleteLater()

    def test_stars_twinkle_in_turn_between_bounds(self, qapp):
        icon = AssistantIcon()
        icon.show()
        icon.set_active(True)
        large, small = [], []
        for _ in range(40):
            QTest.qWait(40)
            large.append(icon._opacity(icon._phase))
            small.append(icon._opacity(icon._phase + 0.5))
        assert min(large) >= icon_module.MIN_OPACITY - 0.01 and max(large) <= 1.0
        assert max(large) - min(large) > 0.3
        assert all(abs((a - icon_module.MIN_OPACITY) + (b - icon_module.MIN_OPACITY) - (1 - icon_module.MIN_OPACITY))
                   < 1e-6 for a, b in zip(large, small)), 'one brightens as the other fades'
        icon.set_active(False)
        assert icon._phase == 0.0

    def test_assistant_icon_is_not_null(self, qapp):
        icon = assistant_icon('#202020', size=24)
        assert not icon.isNull()
        assert not icon.pixmap(24, 24).isNull()

    def test_paints_while_breathing(self, qapp):
        icon = AssistantIcon()
        icon.set_active(True)
        assert not icon.grab().toImage().isNull()
        icon.set_active(False)
