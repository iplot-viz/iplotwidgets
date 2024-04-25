from PySide6.QtGui import QCursor
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtWidgets import QTreeView, QToolTip, QAbstractItemView
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.variableBrowser.models.mtJsonModel import JsonModel, UdaTreeItem
from iplotWidgets.variableBrowser.tools.converters import parse_groups_to_dict, parse_vars_to_dict
from pathlib import Path


class VariableTree(QTreeView):
    def __init__(self):
        super().__init__()
        self.models = {'SEARCH': JsonModel(name='SEARCH', dtype='SEARCH')}
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_menu)
        self.setHeaderHidden(True)
        self.setColumnWidth(0, 205)
        self.setMouseTracking(True)
        self.entered.connect(self.handle_item_entered)
        self.setAlternatingRowColors(True)

        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.expanded.connect(self.expand)
        self.load_model(AppDataAccess.da.defaultds)
        self.dragged_item = None

    def open_menu(self, position):
        index = self.indexAt(position).internalPointer()
        if index.value_type == "nested_variable":
            temp = index.children
            index.children = index.nested_children
            index.nested_children = temp
            self.model().layoutChanged.emit()
            del temp

    def expand(self, index):
        data_source_name = self.parent().get_current_source()
        self.model().expand(index.internalPointer())
        self.model().layoutChanged.emit()

    def load_model(self, data_source):
        data_source_name = data_source.name
        data_source_type = data_source.dtype
        if data_source_name not in self.models:
            self.models[data_source_name] = JsonModel(name=data_source_name, dtype=data_source_type)

        self.setModel(self.models[data_source_name])

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
            f'Unit: {ix.unit}\n'
            f'Description: {ix.description}\n'
            f'DataType: {ix.data_type}',
            self.viewport(),
            self.visualRect(index)
        )

    def dragMoveEvent(self, event):
        if not self.currentIndex().internalPointer().has_child():
            self.dragged_item = self.currentIndex().internalPointer()
            super(VariableTree, self).dragMoveEvent(event)
            return

        event.ignore()
