# Description: Unit tests for TableModel

import unittest
from iplotWidgets.variableBrowser.variableTable import TableModel


class TestTableModel(unittest.TestCase):

    def setUp(self):
        self.model = TableModel()

    def test_initial_dataframe_has_two_columns(self):
        """Test that the model starts with correct columns"""
        self.assertEqual(self.model.columnCount(), 2)
        self.assertListEqual(list(self.model.dataframe.columns), ['DS', 'Variable'])

    def test_initial_dataframe_is_empty(self):
        """Test that the model starts empty"""
        self.assertEqual(self.model.rowCount(), 0)

    def test_add_row_increments_count(self):
        """Test adding rows increases row count"""
        self.model.add_row(['DS1', 'var1'])
        self.assertEqual(self.model.rowCount(), 1)

        self.model.add_row(['DS2', 'var2'])
        self.assertEqual(self.model.rowCount(), 2)


if __name__ == '__main__':
    unittest.main()