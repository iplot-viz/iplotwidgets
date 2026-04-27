# Description: Unit tests for the moduleImporter table model.

import unittest

from PySide6.QtCore import Qt

from iplotWidgets.moduleImporter.moduleTable import ModuleTableModel


class InitialStateTest(unittest.TestCase):
    def test_starts_with_module_column_and_no_rows(self):
        model = ModuleTableModel()
        self.assertEqual(model.columnCount(), 1)
        self.assertEqual(model.rowCount(), 0)
        self.assertListEqual(list(model.dataframe.columns), ['Module'])

    def test_default_total_default_modules_is_zero(self):
        model = ModuleTableModel()
        self.assertEqual(model.total_default_modules, 0)


class AddRowTest(unittest.TestCase):
    def test_add_row_increments_count(self):
        model = ModuleTableModel()
        model.add_row(['numpy'])
        model.add_row(['scipy'])
        self.assertEqual(model.rowCount(), 2)

    def test_added_module_appears_in_data(self):
        model = ModuleTableModel()
        model.add_row(['pandas'])
        idx = model.index(0, 0)
        self.assertEqual(
            model.data(idx, role=Qt.ItemDataRole.DisplayRole), 'pandas')


class RemoveRowTest(unittest.TestCase):
    def test_remove_row_drops_by_index(self):
        model = ModuleTableModel()
        for name in ['numpy', 'scipy', 'pandas']:
            model.add_row([name])

        model.remove_row([1])
        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(list(model.dataframe['Module']), ['numpy', 'pandas'])


class ClearModelTest(unittest.TestCase):
    """``clear_model`` keeps the first ``num`` rows so the default
    modules (always at the top) survive a 'Clear all' click."""

    def test_clear_keeps_first_n_default_modules(self):
        model = ModuleTableModel()
        for name in ['default_a', 'default_b', 'user_x', 'user_y']:
            model.add_row([name])

        model.clear_model(num=2)

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(list(model.dataframe['Module']),
                         ['default_a', 'default_b'])

    def test_clear_with_zero_keeps_no_rows(self):
        model = ModuleTableModel()
        model.add_row(['user_only'])
        model.clear_model(num=0)
        self.assertEqual(model.rowCount(), 0)


class TotalDefaultModulesTest(unittest.TestCase):
    """The CustomItemDelegate paints the first
    ``total_default_modules`` rows in gray to mark them as
    non-removable. Setter/getter must stay symmetric."""

    def test_setter_updates_value(self):
        model = ModuleTableModel()
        model.total_default_modules = 4
        self.assertEqual(model.total_default_modules, 4)


class GetModelListTest(unittest.TestCase):
    def test_returns_list_of_module_names(self):
        model = ModuleTableModel()
        for name in ['a', 'b']:
            model.add_row([name])
        self.assertEqual(model.get_model_list(), ['a', 'b'])


class HeaderDataTest(unittest.TestCase):
    def test_horizontal_header_returns_module_label(self):
        model = ModuleTableModel()
        self.assertEqual(
            model.headerData(0, Qt.Orientation.Horizontal,
                             Qt.ItemDataRole.DisplayRole), 'Module')


if __name__ == '__main__':
    unittest.main()
