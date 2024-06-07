from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel


class PulseTable(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setColumnWidth(0, 100)

        # self.model = PulseTableModel()
        self.models = {'SEARCH': PulseTableModel(data_source=AppDataAccess.da.defaultds)}
        self.current_model = ''

        self.page_size = 20  # pulses per page
        self.page_num = 1  # current page

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(True)

        self.load_model(AppDataAccess.da.defaultds)

        self.adjust_columns(AppDataAccess.da.defaultds)

    def adjust_columns(self, data_source):
        # Adjust
        for column in range(self.models[data_source.name].dataframe.shape[1]):
            self.resizeColumnToContents(column)

    def load_model(self, data_source):
        ds_name = data_source.name
        if ds_name not in self.models:
            self.models[ds_name] = PulseTableModel(data_source=data_source)
            self.models[ds_name].load(self.page_size, self.page_num)

        self.current_model = ds_name
        self.setModel(self.models[ds_name])

    def set_model(self, data_source_name):
        if data_source_name in self.models:
            self.current_model = data_source_name
            self.setModel(self.models[data_source_name])

    def reset_page(self, found: bool = True):
        if found:
            self.page_num = 1
        else:
            self.page_num = 0
