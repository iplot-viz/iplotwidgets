from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView, QToolTip
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.pulseBrowser.models.mtJsonModelPulse import JsonModelPulse


class VariableTreePaging(QTreeView):
    def __init__(self):
        super().__init__()
        self.models = {'SEARCH': JsonModelPulse(data_source=AppDataAccess.da.defaultds, search=True)}
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_menu)
        self.setHeaderHidden(True)
        self.setColumnWidth(0, 205)
        self.setMouseTracking(True)
        self.entered.connect(self.handle_item_entered)
        self.setAlternatingRowColors(True)
        self.load_model(AppDataAccess.da.defaultds)

    def open_menu(self, position):
        index = self.indexAt(position).internalPointer()
        if index.value_type == "nested_variable":
            temp = index.children
            index._children = index.nested_children
            index.nested_children = temp
            self.model().layoutChanged.emit()
            del temp

    def load_model(self, data_source):
        ds_name = data_source.name
        if ds_name not in self.models:
            self.models[ds_name] = JsonModelPulse(data_source=data_source)
            self.models[ds_name].load()

        self.setModel(self.models[ds_name])

    def set_model(self, data_source_name):
        if data_source_name in self.models:
            self.setModel(self.models[data_source_name])

    def handle_item_entered(self, index):
        if not index.isValid():
            return
        ix = index.internalPointer()
        if ix.has_child():
            return
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
