from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView, QToolTip, QAbstractItemView
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataSource import DS_CODAC_TYPE
from iplotWidgets.sizing import FontScaledView
from iplotWidgets.variableBrowser.models.mtJsonModel import VariableModel


class VariableTree(FontScaledView, QTreeView):
    COLUMN_WIDTHS = {0: 205}

    def __init__(self):
        super().__init__()
        self.models = {'SEARCH': VariableModel(data_source=AppDataAccess.da.default_ds, search=True)}
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_menu)
        self.setHeaderHidden(True)
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
        self.doubleClicked.connect(self.toggle_branch)
        self.load_model(AppDataAccess.da.default_ds)
        self.apply_font_metrics()
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

    def toggle_branch(self, index):
        """Collapse an expanded node, otherwise expand its whole branch."""
        if index.isValid() and self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand_branch(index)

    def expand_branch(self, index):
        """Expand a node and every descendant.

        The full walk is only done where the data is already local: Qt
        expands a synoptic or non-CODAC document in one pass, and a CODAC
        search result is recursed so each level still fetches its metadata.
        The lazily loaded CODAC tree expands a single level instead —
        recursing it would fire one blocking server query per level and per
        child on the GUI thread."""
        if not index.isValid():
            return
        model = self.get_model()
        if model.synoptic or model.data_source.source_type != DS_CODAC_TYPE:
            self.expandRecursively(index)
        elif model.search:
            self._expand_loaded_branch(index)
        else:
            QTreeView.expand(self, index)

    def _expand_loaded_branch(self, index):
        # Going through QTreeView.expand keeps the expanded signal firing,
        # so each level loads its metadata before its children are visited.
        QTreeView.expand(self, index)
        model = self.model()
        for row in range(model.rowCount(index)):
            self._expand_loaded_branch(model.index(row, 0, index))

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
