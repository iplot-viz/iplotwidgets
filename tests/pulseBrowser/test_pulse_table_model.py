# Description: Unit tests for PulseTableModel

import unittest
from types import SimpleNamespace

import pandas as pd

from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel


class TestLoadDocumentDefaultSort(unittest.TestCase):

    def setUp(self):
        data_source = SimpleNamespace(source_type='csv')
        self.model = PulseTableModel(data_source=data_source)

    def test_datetime_column_is_sorted_descending(self):
        df = pd.DataFrame({
            'Pulse': ['oldest', 'newest', 'middle'],
            'Time From': pd.to_datetime(
                ['2026-01-01', '2026-03-15', '2026-02-10']),
        })
        self.model.load_document(df)
        self.assertEqual(
            list(self.model.dataframe['Pulse']),
            ['newest', 'middle', 'oldest'])

    def test_string_date_column_is_not_used_for_sorting(self):
        df = pd.DataFrame({
            'pulse': ['a', 'b', 'c'],
            'date': ['2026-01-01', '2026-03-15', '2026-02-10'],
        })
        self.model.load_document(df)
        self.assertEqual(list(self.model.dataframe['pulse']), ['a', 'b', 'c'])

    def test_no_datetime_column_preserves_order(self):
        df = pd.DataFrame({
            'pulse': ['a', 'b', 'c'],
            'value': [1, 2, 3],
        })
        self.model.load_document(df)
        self.assertEqual(list(self.model.dataframe['pulse']), ['a', 'b', 'c'])


if __name__ == '__main__':
    unittest.main()
