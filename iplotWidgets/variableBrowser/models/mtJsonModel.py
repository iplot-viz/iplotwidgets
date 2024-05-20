from typing import Any, List, Dict, Union
from PySide6 import QtGui
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QSize, QPersistentModelIndex

import re

from iplotDataAccess import imasAccess
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataAccess import DataSource
from iplotDataAccess.dataSourceConfig import DS_CODAC_TYPE, DS_IMAS_TYPE
from iplotWidgets.variableBrowser.tools.converters import parse_groups_to_dict, parse_vars_to_dict


class JsonModel(QAbstractItemModel):
    """ An editable model of Json data """

    def __init__(self, data_source: DataSource, parent: QObject = None, search = False):
        super().__init__(parent)

        self.root_item = TreeItem()
        self.data_source = data_source
        self.search = search
        self.clear()

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled

        if index.internalPointer().has_child():
            return Qt.ItemIsEnabled
        else:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

    def mimeTypes(self):
        return ['text/xml']

    def clear(self):
        """ Clear data from the model """
        self.load_document({})

        return None

    def load(self):
        """Load model from zero
        """

        document = AppDataAccess.da.get_cbs_list(data_source_name=self.data_source.name)
        if self.data_source.dtype == DS_CODAC_TYPE:
            document = parse_groups_to_dict(document)

        self.load_document(document)

    def load_document(self, document: dict):
        """Load model from a dictionary
        """

        self.beginResetModel()

        if self.data_source.dtype == DS_IMAS_TYPE:
            self.root_item = ImasTreeItem.load(document)
        elif self.data_source.dtype == DS_CODAC_TYPE:
            self.root_item = UdaTreeItem.load(document)

        self.root_item.check_folder(self.data_source.name)
        self.endResetModel()

    def expand(self, item):
        if self.data_source.dtype != DS_CODAC_TYPE:
            return
        if item.consulted:
            return
        if not self.search:
            path = item.path
            pattern = f'{path}:.*'
            data = AppDataAccess.da.get_var_list(data_source_name=self.data_source.name, pattern=pattern)
            if data:
                data_parsed = parse_vars_to_dict(data, path)
                item.load(data_parsed, item, consulted=True)

        item.check_folder(self.data_source.name)

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        """Override from QAbstractItemModel

        Return data from a json item according index and role

        """
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole:
            if item.is_folder():
                return item.key
            else:
                return f'{item.key} ({item.unit}) {item.data_type}{item.get_dimension_str()}'
        elif role == Qt.EditRole:
            if index.column() == 1:
                return item.key
        elif role == Qt.SizeHintRole:
            "giving size hint"
            return QSize(1000, 20)
        elif role == Qt.DecorationRole:
            if item.value_type == "folder" or item.value_type == "nested_variable":
                return QtGui.QIcon(QtGui.QPixmap("iplotWidgets/iplotWidgets/variableBrowser/icons/folder.svg"))
            elif item.value_type == "variable":
                return QtGui.QIcon(QtGui.QPixmap("iplotWidgets/iplotWidgets/variableBrowser/icons/variable.svg"))

    def index(self, row: int, column: int, parent=QModelIndex()) -> QModelIndex:
        """Override from QAbstractItemModel

        Return index according row, column and parent

        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Override from QAbstractItemModel

        Return parent index of index

        """

        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent

        if parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def children(self, index: QModelIndex) -> List[QModelIndex]:
        if not index.isValid():
            return [QModelIndex()]

        parent_item = index.internalPointer()
        child_item = parent_item.children
        child_list = []
        if not child_item:
            return []
        for item in child_item:
            child_list.append(self.createIndex(item.row(), 0, item))

        return child_list

    def hasChildren(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> bool:
        if parent.column() > 0:
            return False

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.is_folder()

    def rowCount(self, parent=QModelIndex()):
        """Override from QAbstractItemModel

        Return row count from parent index
        """
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.child_count()

    def columnCount(self, parent=QModelIndex()):
        """Override from QAbstractItemModel

        Return column number. For the model, it always returns 1 column
        """
        return 1


class TreeItem:
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'TreeItem' = None, key='', unit='', description='',
                 data_type='', dimension='', value_type='folder'):
        self.parent = parent
        self.key = key
        self.path = ''
        self.unit = unit
        self.description = description
        self.dimension = dimension
        self.data_type = data_type
        self.value_type = value_type
        self.children = []

    def is_folder(self):
        return self.value_type == "folder" or self.value_type == "nested_variable"

    def append_child(self, item: "TreeItem"):
        """Add item as a child"""
        self.children.append(item)

    def child(self, row: int) -> "TreeItem":
        """Return the child of the current item from the given row"""
        return self.children[row]

    def has_child(self) -> bool:
        """Return if the current item has children or not"""
        return bool(self.children)

    def parent(self) -> "TreeItem":
        """Return the parent of the current item"""
        return self.parent

    def child_count(self) -> int:
        """Return the number of children of the current item"""
        return len(self.children)

    def row(self) -> int:
        """Return the row where the current item occupies in the parent"""
        return self.parent.children.index(self) if self.parent else 0

    def get_dimension_str(self):
        pass

    def get_dimension_str_0(self):
        pass

    def load(self, value: Union[List, Dict], parent: "TreeItem" = None,
             path: object = None, consulted: object = False) -> "TreeItem":
        pass

    def check_folder(self, data_source):
        pass


class UdaTreeItem(TreeItem):
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'UdaTreeItem' = None, key='', consulted=False, unit='', description='', data_type='',
                 dimension='', value_type='folder'):
        super().__init__(parent, key, unit, description, data_type, dimension, value_type)
        self.nested_children = []
        self.consulted = consulted

    def get_dimension_str(self):
        if self.dimension == [1]:
            return ''
        else:
            return '[' + ']['.join(str(v) for v in self.dimension) + ']'

    def get_dimension_str_0(self):
        if self.dimension == [1]:
            return ''
        else:
            return '[' + ']['.join('0' for _ in self.dimension) + ']'

    @classmethod
    def load(cls, value: Union[List, Dict], parent: "UdaTreeItem" = None,
             path: object = None, consulted: object = False) -> "UdaTreeItem":
        if path is None:
            path = []
        if consulted:
            root_item = parent
            root_item.consulted = consulted
        else:
            root_item = UdaTreeItem(parent)

        if not isinstance(value, dict):
            return root_item
        items = sorted(value.items(), key=lambda x: (not x[0].isdigit(), x[0]))

        for key, val in items:
            path.append(key)
            child = cls.load(val, root_item, path)
            if val == '':
                child.key = key[:-2]
                child.value_type = "variable"
            else:
                child.key = key
                child.value_type = "folder"
            child.path = '-'.join(path).replace('?V', '')
            root_item.append_child(child)
            path.pop()

        return root_item


    @staticmethod
    def extract_parts(element):
        parts = re.findall(r'(\d+|\D+)', element)
        return [int(part) if part.isdigit() else part for part in parts]

    @classmethod
    def load_nested_child(cls, value: Union[List, Dict], parent: "UdaTreeItem" = None, path: object = None,
                          consulted: object = False) -> "UdaTreeItem":
        if path is None:
            path = []
        if consulted:
            root_item = parent
            root_item.consulted = consulted
        else:
            root_item = TreeItem(parent)
            root_item.path = f"{parent.path}/{path[-1]}"

        if not isinstance(value, dict):
            return root_item

        sorted_key = sorted(value.keys(), key=cls.extract_parts)
        sorted_value = {key: value[key] for key in sorted_key}
        for key, val in sorted_value.items():
            path.append(key)

            if val.keys() == {'type', 'dimensionality', 'units', 'description'}:
                child = TreeItem(root_item)
                child.data_type = val['type']
                child.dimensionality = val['dimensionality']
                child.units = val['units']
                child.description = val['description']
                child.key = f"{root_item.path}/{path[-1]}"
                child.path = key
                child.value_type = "variable"
                child.consulted = True
            else:
                child = cls.load_nested_child(val, root_item, path)
                child.key = key
                child.value_type = "folder"
            if consulted:
                root_item.nested_children.append(child)
            else:
                root_item.append_child(child)
            path.pop()

        return root_item

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

    def check_folder(self, data_source_name):
        self.consulted = True
        for child in self.children:
            if child.has_child() or child.consulted:
                continue
            data = AppDataAccess.da.get_var_fields(data_source_name=data_source_name, variable=child.key)

            if not data:
                continue

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
                UdaTreeItem.load_nested_child(self.group_common_parts(data), child, consulted=True)

                for key, val in data.items():
                    child.append_child(UdaTreeItem(parent=child,
                                                   key=f'{child.key}/{key}',
                                                   consulted=True,
                                                   unit=val['units'],
                                                   description=val['description'],
                                                   dimension=val['dimensionality'],
                                                   data_type=val['type'],
                                                   value_type='variable'
                                                   ))


class ImasTreeItem(TreeItem):
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'ImasTreeItem' = None, key='', unit='', description='', data_type='',
                 dimension='', value_type='folder'):
        super().__init__(parent, key, unit, description, data_type, dimension, value_type)

    def get_dimension_str(self):
        if self.dimension == [1]:
            return ''
        else:
            return '[' + ']['.join(str(v) for v in self.dimension) + ']'

    def get_dimension_str_0(self):
        if self.dimension == [1]:
            return ''
        else:
            return '[' + ']['.join('0' for _ in self.dimension) + ']'

    @classmethod
    def load(cls, value: Union[List, Dict], parent: "ImasTreeItem" = None, path: object = None,
             consulted: object = False) -> "ImasTreeItem":
        if path is None:
            path = []

        root_item = ImasTreeItem(parent)
        if not isinstance(value, dict):
            return root_item

        for key, val in value.items():
            if key not in imasAccess.CBS_ATTR:
                path.append(key)
                child = cls.load(val, root_item, path)
                child.key = key
                child.path = '/'.join(path)
                root_item.append_child(child)
                path.pop()
            else:
                if key == 'documentation':
                    root_item.description = val
                if key == 'data_type':
                    root_item.data_type = val
                if key == 'units':
                    root_item.unit = val
        if all(v in imasAccess.CBS_ATTR for v in value.keys()):
            root_item.value_type = "variable"
        return root_item
