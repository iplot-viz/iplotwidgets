# Description: Unit tests for the Ctrl+C clipboard copy on PulseTable.

import pandas as pd
import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from iplotWidgets.pulseBrowser.PulseTable import PulseTable


@pytest.fixture
def populated_pulse_table(qapp, app_data_access):
    """A PulseTable backed by a small synthetic dataframe.

    The clipboard tests need actual rows and columns to select; the
    fixture wires up a deterministic 2-row × 6-col dataframe so the
    output of Ctrl+C is byte-stable. The model prepends its Selected
    column, so Pulse is view column 1 and Status view column 5.
    """
    table = PulseTable()
    df = pd.DataFrame({
        "Pulse": ["A/1", "B/2"],
        "Time From": pd.to_datetime(["2026-04-01 10:00:00", "2026-04-02 11:00:00"]),
        "Time To": pd.to_datetime(["2026-04-01 10:00:01", "2026-04-02 11:00:01"]),
        "Duration": [pd.Timedelta(seconds=1), pd.Timedelta(seconds=1)],
        "Status": ["completed", "completed"],
        "Description": ["first", "second"],
    })
    model = table.get_current_model()
    model.load_document(df)
    yield table
    table.deleteLater()


def _select_cells(table: PulseTable, rows, cols) -> None:
    sel_model = table.selectionModel()
    sel_model.clearSelection()
    selection = QItemSelection()
    model = table.model()
    for row in rows:
        for col in cols:
            idx = model.index(row, col)
            selection.select(idx, idx)
    sel_model.select(selection, QItemSelectionModel.SelectionFlag.Select)


def _press_copy(table: PulseTable) -> None:
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C,
                      Qt.KeyboardModifier.ControlModifier, "c")
    table.keyPressEvent(event)


class TestPulseTableCopySingleColumn:
    def test_no_selection_does_not_change_clipboard(self, populated_pulse_table):
        QApplication.clipboard().setText("baseline")
        _press_copy(populated_pulse_table)
        assert QApplication.clipboard().text() == "baseline"

    def test_single_column_selection_copies_without_header(self, populated_pulse_table):
        _select_cells(populated_pulse_table, rows=[0, 1], cols=[1])
        _press_copy(populated_pulse_table)

        # Single column: header row is skipped (matches statistics-table behaviour).
        # Row order is the dataframe order after the default datetime DESC sort.
        clipboard = QApplication.clipboard().text()
        assert clipboard == "B/2\nA/1"


class TestPulseTableCopyMultipleColumns:
    def test_multi_column_selection_includes_header_row(self, populated_pulse_table):
        _select_cells(populated_pulse_table, rows=[0], cols=[1, 5])
        _press_copy(populated_pulse_table)

        clipboard = QApplication.clipboard().text()
        # Header row + data row, tab-separated, newline-separated.
        # Row 0 of the sorted dataframe is "B/2" (newest after default DESC sort).
        lines = clipboard.split("\n")
        assert len(lines) == 2
        assert lines[0] == "Pulse\tStatus"
        assert lines[1] == "B/2\tcompleted"

    def test_multi_row_multi_column_preserves_order(self, populated_pulse_table):
        _select_cells(populated_pulse_table, rows=[1, 0], cols=[5, 1])
        _press_copy(populated_pulse_table)

        clipboard = QApplication.clipboard().text()
        lines = clipboard.split("\n")
        # Header row + 2 data rows. Rows and columns are emitted in
        # ascending index order regardless of selection order.
        assert len(lines) == 3
        assert lines[0] == "Pulse\tStatus"
        assert lines[1] == "B/2\tcompleted"
        assert lines[2] == "A/1\tcompleted"


class TestPulseTableCopyOtherKeys:
    def test_non_copy_keypress_falls_through_to_super(self, populated_pulse_table):
        """Pressing a non-Copy key must not clear or alter the clipboard."""
        QApplication.clipboard().setText("untouched")
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A,
                          Qt.KeyboardModifier.NoModifier, "a")
        populated_pulse_table.keyPressEvent(event)
        assert QApplication.clipboard().text() == "untouched"
