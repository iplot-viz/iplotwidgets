"""
Tests for iplotWidgets.sizing.

The views in this package are sized in characters and font height rather than
pixels so they track the application font, which is how MINT implements its UI
scale. These tests use bare Qt views instead of the real tables so they do not
need a data source.
"""

import unittest

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView, QTreeView

from iplotWidgets.sizing import FontScaledView, char_width, row_height


def ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


class ScaledTable(FontScaledView, QTableView):
    COLUMN_CHARS = {0: 14}

    def __init__(self):
        QTableView.__init__(self)
        # setColumnWidth is a no-op without a model, which is why the real views
        # call apply_font_metrics only once they have one.
        self.setModel(QStandardItemModel(3, 2))
        self.apply_font_metrics()


class ScaledTree(FontScaledView, QTreeView):
    COLUMN_CHARS = {0: 26}

    def __init__(self):
        QTreeView.__init__(self)
        self.setModel(QStandardItemModel(3, 2))
        self.apply_font_metrics()


class SizingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = ensure_qapp()

    def setUp(self):
        self._font = self.app.font()

    def tearDown(self):
        self.app.setFont(self._font)

    def _bigger_font(self, widget, factor=2.0):
        font = widget.font()
        font.setPointSizeF(font.pointSizeF() * factor)
        return font

    def test_char_width_grows_with_the_font(self):
        table = ScaledTable()
        small = char_width(table, 14)
        table.setFont(self._bigger_font(table))
        self.assertGreater(char_width(table, 14), small)

    def test_row_height_leaves_room_for_the_text(self):
        table = ScaledTable()
        self.assertGreater(row_height(table), table.fontMetrics().height())

    def test_fixed_rows_still_fit_a_larger_font(self):
        # The regression this guards: a Fixed vertical header keeps whatever
        # defaultSectionSize it resolved at construction, so a larger font used
        # to clip the rows.
        table = ScaledTable()
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.apply_font_metrics()
        before = table.verticalHeader().defaultSectionSize()

        table.setFont(self._bigger_font(table))
        self.app.processEvents()
        after = table.verticalHeader().defaultSectionSize()

        self.assertGreater(after, before)
        self.assertGreaterEqual(after, table.fontMetrics().height())

    def test_column_width_is_reapplied_on_font_change(self):
        table = ScaledTable()
        table.apply_font_metrics()
        before = table.columnWidth(0)
        table.setFont(self._bigger_font(table))
        self.app.processEvents()
        self.assertGreater(table.columnWidth(0), before)

    def test_tree_without_vertical_header_is_handled(self):
        # QTreeView has no verticalHeader(); the mixin must not assume one.
        tree = ScaledTree()
        tree.apply_font_metrics()
        self.assertGreater(tree.columnWidth(0), 0)

    def test_char_width_survives_a_zero_average_width(self):
        class OddMetrics:
            def averageCharWidth(self):
                return 0

            def horizontalAdvance(self, _text):
                return 0

            def height(self):
                return 10

        class Widget:
            def fontMetrics(self):
                return OddMetrics()

        self.assertEqual(char_width(Widget(), 10), 80)


if __name__ == '__main__':
    unittest.main()
