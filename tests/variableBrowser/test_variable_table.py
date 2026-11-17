# Description: Unit tests for the variable browser table model.

import unittest

from PySide6.QtCore import Qt

from iplotWidgets.variableBrowser.variableTable import TableModel


class InitialStateTest(unittest.TestCase):
    def setUp(self):
        self.model = TableModel()

    def test_initial_dataframe_has_two_columns(self):
        self.assertEqual(self.model.columnCount(), 2)
        self.assertListEqual(list(self.model.dataframe.columns),
                             ['DS', 'Variable'])

    def test_initial_dataframe_is_empty(self):
        self.assertEqual(self.model.rowCount(), 0)


class AddRowTest(unittest.TestCase):
    def setUp(self):
        self.model = TableModel()

    def test_add_row_increments_count(self):
        self.model.add_row(['DS1', 'var1'])
        self.assertEqual(self.model.rowCount(), 1)

        self.model.add_row(['DS2', 'var2'])
        self.assertEqual(self.model.rowCount(), 2)

    def test_added_rows_are_retrievable_via_data(self):
        self.model.add_row(['csv', 'temperature'])
        idx = self.model.index(0, 1)
        value = self.model.data(idx, role=Qt.ItemDataRole.DisplayRole)
        self.assertEqual(value, 'temperature')


class DragTest(unittest.TestCase):
    """The rows selected can be dragged out of the table; a press on another row selects as before, also by dragging."""

    def setUp(self):
        from PySide6.QtWidgets import QApplication
        from iplotWidgets.variableBrowser.variableTable import VariableTable
        self.app = QApplication.instance() or QApplication([])
        self.table = VariableTable()
        self.addCleanup(self.table.deleteLater)
        for name in ('a', 'b', 'c', 'd'):
            self.table.model.add_row(['csv', name])
        self.table.resize(400, 300)
        self.table.show()
        self.app.processEvents()
        self.drags = []
        self.table.startDrag = self.drags.append

    def _press_and_move(self, from_row: int, to_row: int) -> list:
        """The rows selected after a press on a row and a move down to another with the button held."""
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtTest import QTest
        viewport = self.table.viewport()
        first = self.table.visualRect(self.table.model.index(from_row, 1)).center()
        last = self.table.visualRect(self.table.model.index(to_row, 1)).center()
        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, first)
        for step in range(1, 11):
            point = QPointF(first.x(), first.y() + (last.y() - first.y()) * step / 10)
            self.app.sendEvent(viewport, QMouseEvent(QEvent.Type.MouseMove, point, viewport.mapToGlobal(point),
                                                     Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                                     Qt.KeyboardModifier.NoModifier))
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, last)
        return sorted({index.row() for index in self.table.selectionModel().selectedIndexes()})

    def test_a_press_on_a_row_not_selected_and_a_move_select_the_rows_passed(self):
        self.assertEqual(self._press_and_move(0, 2), [0, 1, 2])
        self.assertEqual(self.drags, [])

    def test_the_rows_selected_are_dragged_and_nothing_can_be_dropped_on_the_table(self):
        self.table.selectRow(1)

        self._press_and_move(1, 3)

        self.assertEqual(len(self.drags), 1)
        self.assertTrue(self.table.model.flags(self.table.model.index(0, 1)) & Qt.ItemFlag.ItemIsDragEnabled)
        self.assertFalse(self.table.acceptDrops())
        self.assertEqual(self.table.model.supportedDragActions(), Qt.DropAction.CopyAction)


class RemoveRowsTest(unittest.TestCase):
    def setUp(self):
        self.model = TableModel()
        for i in range(3):
            self.model.add_row([f'ds{i}', f'var{i}'])

    def test_remove_rows_drops_by_index(self):
        self.model.remove_rows([1])
        self.assertEqual(self.model.rowCount(), 2)
        self.assertEqual(list(self.model.dataframe['Variable']),
                         ['var0', 'var2'])

    def test_remove_multiple_rows_at_once(self):
        self.model.remove_rows([0, 2])
        self.assertEqual(self.model.rowCount(), 1)
        self.assertEqual(list(self.model.dataframe['Variable']), ['var1'])


class ClearModelTest(unittest.TestCase):
    def test_clear_resets_to_empty_dataframe_with_columns(self):
        model = TableModel()
        model.add_row(['ds', 'var'])
        model.clear_model()

        self.assertEqual(model.rowCount(), 0)
        self.assertListEqual(list(model.dataframe.columns), ['DS', 'Variable'])


class HeaderDataTest(unittest.TestCase):
    def test_horizontal_header_returns_column_names(self):
        model = TableModel()
        self.assertEqual(
            model.headerData(0, Qt.Orientation.Horizontal,
                             Qt.ItemDataRole.DisplayRole), 'DS')
        self.assertEqual(
            model.headerData(1, Qt.Orientation.Horizontal,
                             Qt.ItemDataRole.DisplayRole), 'Variable')

    def test_vertical_header_returns_none(self):
        """The variable table has no row headers; the model must return
        ``None`` so Qt falls back to the row number."""
        model = TableModel()
        self.assertIsNone(
            model.headerData(0, Qt.Orientation.Vertical,
                             Qt.ItemDataRole.DisplayRole))


class GetModelListTest(unittest.TestCase):
    def test_returns_list_of_lists(self):
        model = TableModel()
        model.add_row(['csv', 'a'])
        model.add_row(['uda', 'b'])
        result = model.get_model_list()
        self.assertEqual(result, [['csv', 'a'], ['uda', 'b']])


if __name__ == '__main__':
    unittest.main()
