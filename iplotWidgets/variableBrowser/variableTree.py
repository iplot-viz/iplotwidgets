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
        # level, wherever the data is already local (see expand_branch).
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
        """Expand a node, recursively only where the data is already local.

        A synoptic tree carries its metadata with it (every item is marked
        consulted by ``apply_metadata``) and a non-CODAC document is fully
        loaded, so Qt can unfold either in one pass at no cost.

        Everything else — a CODAC search result as much as the lazily loaded
        CODAC tree — opens a single level, exactly as a single click does.
        Expanding a level runs ``check_folder``, which fires one blocking
        ``get_var_fields`` query per unconsulted child on the GUI thread, so
        recursing a branch costs one server round trip per variable under it
        and freezes the browser for as long as that takes. The user opens the
        levels they need instead, one bounded query at a time."""
        if not index.isValid():
            return
        model = self.get_model()
        if model.synoptic or model.data_source.source_type != DS_CODAC_TYPE:
            self.expandRecursively(index)
        else:
            QTreeView.expand(self, index)

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
