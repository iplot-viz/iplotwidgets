"""
The widgets draw in a dark palette, in its colours, what they draw in a light one: the default modules of the
module table and the selected pulses keep their colours in a light palette and darken in a dark one.
"""

import unittest
from types import SimpleNamespace

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QStandardItemModel
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem, QTableView

from iplotWidgets.moduleImporter.moduleTable import CustomItemDelegate
from iplotWidgets.palette import blend, is_dark
from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel


def ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _dark_palette() -> QPalette:
    palette = QPalette()
    for role, colour in (('Window', '#1e1e1e'), ('WindowText', '#ffffff'), ('Base', '#2d2d2d'),
                         ('Text', '#ffffff')):
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
    return palette


class PaletteTest(unittest.TestCase):
    def setUp(self):
        self.app = ensure_qapp()
        self.addCleanup(self.app.setPalette, QPalette())

    def test_is_dark_and_blend(self):
        self.assertFalse(is_dark())
        self.assertTrue(is_dark(_dark_palette()))
        self.assertEqual(blend('#000000', '#ffffff', 0.5).name(), '#808080')

    def _default_module_background(self, palette: QPalette) -> QColor:
        table = QTableView()
        self.addCleanup(table.deleteLater)
        # The module table keeps its model as an attribute: the delegate reads how many are default from it.
        table.model = SimpleNamespace(total_default_modules=1)
        option = QStyleOptionViewItem()
        option.palette = palette
        option.widget = table
        cells = QStandardItemModel(1, 1)
        CustomItemDelegate().initStyleOption(option, cells.index(0, 0))
        return option.backgroundBrush.color()

    def test_the_default_modules_are_grey_in_the_colours_of_the_palette(self):
        light = QPalette()
        light.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
        light.setColor(QPalette.ColorRole.Text, QColor('#000000'))
        self.assertEqual(self._default_module_background(light), QColor(200, 200, 200))
        self.assertLess(self._default_module_background(_dark_palette()).lightness(), 128)

    def test_the_selected_pulses_are_yellow_on_the_base_of_the_palette(self):
        model = PulseTableModel(data_source=SimpleNamespace(source_type='csv'))
        model.load_document(pd.DataFrame({'Pulse': ['A', 'B']}))
        model.set_selected_pulses(['A'])
        column = model.dataframe.columns.get_loc('Pulse')
        row = next(r for r in range(model.rowCount())
                   if model.data(model.index(r, column), Qt.ItemDataRole.DisplayRole) == 'A')
        index = model.index(row, column)
        self.assertEqual(model.data(index, Qt.ItemDataRole.BackgroundRole).color(), QColor(255, 244, 200))
        self.app.setPalette(_dark_palette())
        self.assertLess(model.data(index, Qt.ItemDataRole.BackgroundRole).color().lightness(), 128)


if __name__ == "__main__":
    unittest.main()
