# Description: Unit tests for ConsoleWidget log routing and severity filtering.

import logging
import unittest

import pytest

from iplotWidgets.consoleWidget.consoleWidget import ConsoleWidget


@pytest.fixture
def console(qapp):
    """Build a ConsoleWidget per test and clean its handler off the
    root logger when done — otherwise handler leakage between tests
    causes log calls in later tests to spam every previous widget."""
    widget = ConsoleWidget()
    yield widget
    root = logging.getLogger()
    if widget.log_handler in root.handlers:
        root.removeHandler(widget.log_handler)
    widget.deleteLater()


def _make_record(level: int, message: str = "test") -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=level, pathname=__file__,
        lineno=1, msg=message, args=(), exc_info=None)


class SeverityFilterTest:
    """``log_emit`` honours the combo-box level — anything below the
    selected severity is dropped silently. The default is ``WARNING``,
    which matches the combo's ``setCurrentText('WARNING')`` at init."""

    def test_default_severity_is_warning(self, console):
        assert console.severity_level.currentText() == 'WARNING'

    def test_record_below_threshold_is_dropped(self, console):
        console.severity_level.setCurrentText('WARNING')
        console.setup_logging()
        console.log_emit(_make_record(logging.DEBUG, "noise"))
        assert console.content.toPlainText() == ""

    def test_record_at_threshold_is_emitted(self, console):
        console.severity_level.setCurrentText('WARNING')
        console.setup_logging()
        console.log_emit(_make_record(logging.WARNING, "warn-msg"))
        assert "warn-msg" in console.content.toPlainText()

    def test_record_above_threshold_is_emitted(self, console):
        console.severity_level.setCurrentText('WARNING')
        console.setup_logging()
        console.log_emit(_make_record(logging.ERROR, "err-msg"))
        assert "err-msg" in console.content.toPlainText()

    def test_changing_threshold_at_runtime_takes_effect(self, console):
        console.severity_level.setCurrentText('ERROR')
        console.setup_logging()
        # WARNING is now below the threshold and must be dropped.
        console.log_emit(_make_record(logging.WARNING, "filtered"))
        assert "filtered" not in console.content.toPlainText()


class HtmlFormattingTest:
    """Each level maps to a distinct hex color so users can scan a busy
    console at a glance. The mapping must stay stable; changing colors
    intentionally is a separate decision."""

    @pytest.mark.parametrize('level_name, expected_color', [
        ('DEBUG', '#A0A0A0'),
        ('INFO', '#00CC00'),
        ('WARNING', '#FFA500'),
        ('ERROR', '#FF0000'),
        ('CRITICAL', '#8B0000'),
    ])
    def test_level_color_is_applied_in_html(self, console, level_name,
                                              expected_color):
        # Loosen the threshold so every level is emitted regardless.
        console.severity_level.setCurrentText('DEBUG')
        console.setup_logging()
        console.log_emit(_make_record(getattr(logging, level_name),
                                      f"{level_name}-line"))
        rendered = console.content.document().toHtml()
        assert expected_color.lower() in rendered.lower()


class ClearConsoleTest:
    def test_clear_console_empties_text(self, console):
        console.severity_level.setCurrentText('DEBUG')
        console.setup_logging()
        console.log_emit(_make_record(logging.WARNING, "hello"))
        assert "hello" in console.content.toPlainText()
        console.clear_console()
        assert console.content.toPlainText() == ""


# Expose pytest-style classes so collection picks them up.
TestSeverityFilter = SeverityFilterTest
TestHtmlFormatting = HtmlFormattingTest
TestClearConsole = ClearConsoleTest
