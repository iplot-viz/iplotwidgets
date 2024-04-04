from PySide6.QtGui import QCursor
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtWidgets import QTreeView, QToolTip, QAbstractItemView
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.variableBrowser.models.mtJsonModel import JsonModel, TreeItem
from iplotWidgets.variableBrowser.tools.converters import parse_groups_to_dict, parse_vars_to_dict
from pathlib import Path


class VariableTree(QTreeView):
    def __init__(self):
        super().__init__()
        self.models = {'SEARCH': JsonModel(name='SEARCH')}
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)
        self.setHeaderHidden(True)
        self.setColumnWidth(0, 205)
        self.setMouseTracking(True)
        self.entered.connect(self.handle_item_entered)
        self.setAlternatingRowColors(True)

        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.expanded.connect(self.expand)
        self.load_model(AppDataAccess.da.get_default_ds_name())
        self.dragged_item = None

    def openMenu(self, position):
        index = self.indexAt(position).internalPointer()
        if index.value_type == "nested_variable":
            temp = index.children
            index._children = index.nested_children
            index.nested_children = temp
            self.model().layoutChanged.emit()
            del temp

    def expand(self, index):
        data_source_name = self.parent().get_current_source()
        if index.internalPointer().consulted:
            return
        if self.model().name != 'SEARCH':
            path = index.internalPointer().path
            pattern = f'{path}:.*'
            data = AppDataAccess.da.get_var_list(data_source_name=data_source_name, pattern=pattern)
            if data:
                data_parsed = parse_vars_to_dict(data, path)
                self.model().add_children(parent=index.internalPointer(), document=data_parsed)

        self.check_folder(index.internalPointer(), data_source_name)
        index.internalPointer().consulted = True
        self.model().layoutChanged.emit()

    @staticmethod
    def group_common_parts(data):
        common_parts = {}

        for key, value in data.items():
            sub_data = common_parts
            parts = key.split('/')

            for parte in parts[:-1]:
                if parte not in sub_data:
                    sub_data[parte] = {}

                sub_data = sub_data[parte]

            sub_data[parts[-1]] = value

        return common_parts

    def check_folder(self, index, data_source_name):
        for child in index.children:
            if child.has_child() or child.consulted:
                continue
            data = AppDataAccess.da.get_var_fields(data_source_name=data_source_name, variable=child.key)

            if data:
                if set(data.keys()) == {'status_id', 'val', 'secs', 'severity_id', 'nanosecs'}:
                    child.data_type = data['val']['type']
                    child.unit = data['val']['units']
                    child.description = data['val']['description']
                    child.dimension = data['val']['dimensionality']
                elif list(data.keys()) == ['value']:
                    child.data_type = data['value']['type']
                    child.unit = data['value']['units']
                    child.description = data['value']['description']
                    child.dimension = data['value']['dimensionality']
                else:
                    child.value_type = 'nested_variable'
                    TreeItem.load_nested_child(self.group_common_parts(data), child, consulted=True)

                    for key, val in data.items():
                        child.append_child(TreeItem(parent=child,
                                                    key=f'{child.key}/{key}',
                                                    consulted=True,
                                                    unit=val['units'],
                                                    description=val['description'],
                                                    dimension=val['dimensionality'],
                                                    data_type=val['type'],
                                                    value_type='variable'
                                                    ))

    def load_model(self, data_source_name):
        if data_source_name not in self.models:

            self.models[data_source_name] = JsonModel(name=data_source_name)
            lines = AppDataAccess.da.get_cbs_list(data_source_name=data_source_name)
            if lines:
                document = parse_groups_to_dict(lines)
                self.models[data_source_name].load(document)
            else:
                file_path = QFileInfo(__file__).absoluteDir().filePath(f"{data_source_name}.txt")
                if Path(file_path).is_file():
                    with open(file_path, encoding='utf-8') as file:
                        lines = file.read().split('\n')
                        document = parse_groups_to_dict(lines)
                        self.models[data_source_name].load(document)

            self.check_folder(self.models[data_source_name].root_item, data_source_name)

        self.setModel(self.models[data_source_name])

    def set_model(self, data_source_name):
        if data_source_name in self.models:
            self.setModel(self.models[data_source_name])

    def clear_model(self):
        self.setModel(None)

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
