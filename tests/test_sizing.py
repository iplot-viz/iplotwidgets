"""
Tests for iplotWidgets.sizing.

The views in this package keep their pixel sizes at the platform font and grow
them with the application font, which is how MINT implements its UI scale.
These tests use bare Qt views instead of the real tables so they do not need a
data source.
"""

import unittest

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView, QTreeView

from iplotWidgets.sizing import FontScaledView, clamp_to_screen, font_scale, row_height, scaled_px


def ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


class ScaledTable(FontScaledView, QTableView):
    COLUMN_WIDTHS = {0: 100}

    def __init__(self):
        QTableView.__init__(self)
        # setColumnWidth is a no-op without a model, which is why the real views
        # call apply_font_metrics only once they have one.
        self.setModel(QStandardItemModel(3, 2))
        self.apply_font_metrics()


class ScaledTree(FontScaledView, QTreeView):
    COLUMN_WIDTHS = {0: 205}

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

    def test_sizes_are_the_pixel_literals_at_the_platform_font(self):
        table = ScaledTable()
        self.assertAlmostEqual(font_scale(table), 1.0, places=6)
        self.assertEqual(scaled_px(table, 100), 100)
        self.assertEqual(table.columnWidth(0), 100)

    def test_sizes_grow_with_the_font(self):
        table = ScaledTable()
        table.setFont(self._bigger_font(table))
        self.assertGreater(font_scale(table), 1.5)
        self.assertGreater(scaled_px(table, 100), 150)

    def test_row_height_leaves_room_for_the_text(self):
        table = ScaledTable()
        self.assertGreater(row_height(table), table.fontMetrics().height())

    def test_rows_keep_the_style_default_until_the_font_outgrows_it(self):
        # At the default font the rows must look exactly as they always did.
        plain = QTableView()
        style_default = plain.verticalHeader().defaultSectionSize()
        table = ScaledTable()
        self.assertEqual(table.verticalHeader().defaultSectionSize(), max(style_default, row_height(table)))
        table.setFont(self._bigger_font(table, factor=3.0))
        self.app.processEvents()
        self.assertGreater(table.verticalHeader().defaultSectionSize(), style_default)

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



class ClampToScreenTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = ensure_qapp()

    def test_a_fitting_size_is_kept(self):
        widget = QTableView()
        clamp_to_screen(widget, 300, 200)
        self.assertEqual((widget.width(), widget.height()), (300, 200))

    def test_an_oversized_window_is_cut_to_its_screen(self):
        widget = QTableView()
        available = widget.screen().availableGeometry()
        clamp_to_screen(widget, available.width() * 4, available.height() * 4)
        self.assertLessEqual(widget.width(), available.width() * 0.9)
        self.assertLessEqual(widget.height(), available.height() * 0.9)


if __name__ == '__main__':
    unittest.main()
