from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QTableView, QAbstractItemView, QHeaderView

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel


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

    def set_model(self, ds_name):
        if ds_name in self.models:
            self.current_model_name = ds_name
            self.setModel(self.models[ds_name])

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

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection_to_clipboard()
            return
        super().keyPressEvent(event)

    def _copy_selection_to_clipboard(self):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        rows = sorted({idx.row() for idx in indexes})
        cols = sorted({idx.column() for idx in indexes})
        model = self.model()
        lines = []
        if len(cols) > 1:
            headers = [str(model.headerData(c, Qt.Orientation.Horizontal,
                                            Qt.ItemDataRole.DisplayRole) or '')
                       for c in cols]
            lines.append('\t'.join(headers))
        for row in rows:
            values = []
            for col in cols:
                value = model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole)
                values.append('' if value is None else str(value))
            lines.append('\t'.join(values))
        QApplication.clipboard().setText('\n'.join(lines))
