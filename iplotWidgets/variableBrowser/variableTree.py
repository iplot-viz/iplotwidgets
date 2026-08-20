from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView, QToolTip, QAbstractItemView
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.variableBrowser.models.mtJsonModel import VariableModel


class VariableTree(QTreeView):
    def __init__(self):
        super().__init__()
        self.models = {'SEARCH': VariableModel(data_source=AppDataAccess.da.default_ds, search=True)}
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
        # Double-click expands the whole branch instead of toggling one
        # level, so search results do not have to be unfolded by hand.
        self.setExpandsOnDoubleClick(False)
        self.doubleClicked.connect(self.expand_branch)
        self.load_model(AppDataAccess.da.default_ds)
        self.dragged_item = None

    def get_model(self) -> VariableModel:
        return self.model()

    def open_menu(self, position):
        index = self.indexAt(position).internalPointer()
        if index.data_type == "nested_variable":
            temp = index.children
            index.children = index.nested_children
            index.nested_children = temp
            self.get_model().layoutChanged.emit()
            del temp

    def expand(self, index):
        self.get_model().expand(index.internalPointer())
        self.get_model().layoutChanged.emit()

    def expand_branch(self, index):
        """Expand a node and every descendant. Going through QTreeView.expand
        keeps the expanded signal firing, so lazily loaded levels are fetched
        before their own children are visited."""
        if not index.isValid():
            return
        QTreeView.expand(self, index)
        model = self.model()
        for row in range(model.rowCount(index)):
            self.expand_branch(model.index(row, 0, index))

    def load_model(self, data_source):
        ds_name = data_source.name
        if ds_name not in self.models:
            self.models[ds_name] = VariableModel(data_source=data_source)
            self.models[ds_name].load()

        self.setModel(self.models[ds_name])

    def load_hmi_model(self, data_source, document, metadata):
        key = f'{data_source.name}:HMI'
        if key not in self.models:
            self.models[key] = VariableModel(data_source=data_source)
        self.models[key].load_document(document, metadata=metadata)
        self.setModel(self.models[key])

    def set_model(self, data_source_name):
        if data_source_name in self.models:
            self.setModel(self.models[data_source_name])

    def handle_item_entered(self, index):
        if not index.isValid():
            return
        ix = index.internalPointer()
        if ix.has_child():
            return
        # Synoptic leaves already show unit, data type and description in
        # their label; a tooltip would only repeat it.
        if getattr(ix, 'synoptic', False):
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
