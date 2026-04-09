from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor, QPalette
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView, QStyledItemDelegate, QApplication, QStyleOptionViewItem

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel


class _LinkDelegate(QStyledItemDelegate):
    """Renders cells as blue underlined links."""
    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        option.palette.setColor(QPalette.ColorRole.Text, QColor("#0078D4"))
        font = option.font
        font.setUnderline(True)
        option.font = font


class PulseTable(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setColumnWidth(0, 100)

        self.models = {'SEARCH': PulseTableModel(data_source=AppDataAccess.da.default_ds)}
        self.current_model_name = ''

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(True)

        self.load_model(AppDataAccess.da.default_ds)
        self.adjust_columns(AppDataAccess.da.default_ds)
        self.clicked.connect(self._on_cell_clicked)

    def adjust_columns(self, data_source):
        # Adjust
        for column in range(self.models[data_source.name].dataframe.shape[1]):
            self.resizeColumnToContents(column)

    def load_model(self, data_source):
        ds_name = data_source.name
        if ds_name not in self.models:
            self.models[ds_name] = PulseTableModel(data_source=data_source)
            self.models[ds_name].load()

        self.current_model_name = ds_name
        self.setModel(self.models[ds_name])
        self._apply_link_delegate()

    def _apply_link_delegate(self):
        """Apply link delegate to the alias column."""
        model = self.get_current_model()
        if "alias" in model.dataframe.columns:
            for display_col in range(model.columnCount()):
                df_col = model._get_visible_col_index(display_col)
                if df_col >= 0 and model.dataframe.columns[df_col] == "alias":
                    self.setItemDelegateForColumn(display_col, _LinkDelegate(self))
                    break

    def _on_cell_clicked(self, index):
        model = self.get_current_model()
        df_col = model._get_visible_col_index(index.column())
        if df_col >= 0 and model.dataframe.columns[df_col] == "alias":
            url = model.get_dashboard_link(index.row())
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def set_model(self, ds_name):
        if ds_name in self.models:
            self.current_model_name = ds_name
            self.setModel(self.models[ds_name])
            self._apply_link_delegate()

    def get_current_model(self) -> PulseTableModel:
        return self.models[self.current_model_name]

    def get_page_size(self):
        return self.get_current_model().page_size

    def get_total_pages(self):
        return self.get_current_model().get_total_pages()

    def get_current_page(self):
        return self.get_current_model().get_real_page()

    def get_pulse_info(self, row):
        self.get_current_model().get_pulse_info(row)

    def get_imas_uri(self, row: int) -> str:
        return self.get_current_model().get_imas_uri(row)

    def get_dashboard_link(self, row: int) -> str:
        return self.get_current_model().get_dashboard_link(row)
