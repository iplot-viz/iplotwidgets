from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView, QToolTip

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

        self.model = PulseTableModel()
        self.page_size = 20  # pulses per page
        self.page_num = 1  # current page

        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.setMouseTracking(True)

        self.entered.connect(self.handle_item_entered)
        self.setAlternatingRowColors(True)

        self.load_model(AppDataAccess.da.defaultds)

    def load_model(self, data_source):
        self.model.load(data_source, self.page_size, self.page_num)
        self.setModel(self.model)

    def set_model(self):
        self.setModel(self.model)

    def handle_item_entered(self, index):
        if not index.isValid():
            return
        pulse_index = index.row()
        ix = self.model.get_pulse(pulse_index)

        QToolTip.showText(
            QCursor.pos(),
            f'{ix.key}\n'
            f'Description: {ix.description}\n'
            f'Status: {ix.status}\n'
            f'Time From: {ix.timeFrom}\n'
            f'Time To: {ix.timeTo}\n'
            f'Duration: {ix.duration}\n',
            self.viewport(),
            self.visualRect(index)
        )

    def reset_page(self, found: bool = True):
        if found:
            self.page_num = 1
        else:
            self.page_num = 0
