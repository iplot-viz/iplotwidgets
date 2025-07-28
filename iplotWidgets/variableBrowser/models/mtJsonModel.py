from typing import Any, List, Dict, Union
from PySide6 import QtGui
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QSize, QPersistentModelIndex
import re

from iplotDataAccess.dataSource import DataSource, DS_IMASPY_TYPE, DS_CODAC_TYPE, DS_CSV_TYPE


class VariableModel(QAbstractItemModel):
    """ An editable model of Json data """

    def __init__(self, data_source: DataSource, parent: QObject = None, search=False):
        super().__init__(parent)

        self.root_item = VarItem()
        self.data_source = data_source
        self.search: bool = search
        self.clear()

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled

        if index.internalPointer().has_child():
            return Qt.ItemFlag.ItemIsEnabled
        else:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled

    def mimeTypes(self):
        return ['text/xml']

    def clear(self):
        """ Clear data from the model """
        self.load_document({})

        return None

    def load(self):
        """Load model from zero
        """

        document = self.data_source.get_cbs_dict()
        self.load_document(document)

    def load_document(self, document: dict):
        """Load model from a dictionary
        """

        self.beginResetModel()

        if self.data_source.source_type == DS_IMASPY_TYPE:
            self.root_item = ImasVarItem.load(document)
        elif self.data_source.source_type == DS_CODAC_TYPE or self.data_source.source_type == DS_CSV_TYPE: 
            self.root_item = UdaVarItem.load(document, UdaVarItem(data_type="folder"), consulted=True)

        self.root_item.check_folder(self.data_source)
        self.endResetModel()

    def expand(self, item):
        if self.data_source.source_type != DS_CODAC_TYPE:
            return
        if item.consulted:
            return
        if not self.search:
            path = item.path
            pattern = f'{path}:.*'
            data = self.data_source.get_var_dict(pattern=pattern, path=path)
            if data:
                item.load(data, item, consulted=True)

        item.check_folder(self.data_source)

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        """Override from QAbstractItemModel

        Return data from a json item according index and role

        """
        if not index.isValid():
            return None

        item = index.internalPointer()  # type: VarItem

        if role == Qt.ItemDataRole.DisplayRole:
            if item.is_folder():
                return item.get_folder_str()
            else:
                return item.get_tree_variable_str()
        elif role == Qt.ItemDataRole.EditRole:
            if index.column() == 1:
                return item.key
        elif role == Qt.ItemDataRole.SizeHintRole:
            "giving size hint"
            return QSize(1000, 20)
        elif role == Qt.ItemDataRole.DecorationRole:
            if item.is_folder():
                return QtGui.QIcon(QtGui.QPixmap("iplotWidgets/iplotWidgets/variableBrowser/icons/folder.svg"))
            else:
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


class VarItem:
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'VarItem' = None, key='', unit='', description='', data_type='', dimension=''):
        self.parent = parent
        self.key = key
        self.path = ''
        self.unit = unit
        self.description = description
        self.dimension = dimension
        self.data_type = data_type
        self.children = []

    def is_folder(self) -> bool:
        pass

    def append_child(self, item: "VarItem"):
        """Add item as a child"""
        self.children.append(item)

    def child(self, row: int) -> "VarItem":
        """Return the child of the current item from the given row"""
        return self.children[row]

    def has_child(self) -> bool:
        """Return if the current item has children or not"""
        return bool(self.children)

    def parent(self) -> "VarItem":
        """Return the parent of the current item"""
        return self.parent

    def child_count(self) -> int:
        """Return the number of children of the current item"""
        return len(self.children)

    def row(self) -> int:
        """Return the row where the current item occupies in the parent"""
        return self.parent.children.index(self) if self.parent else 0

    def load(self, value: Union[List, Dict], parent: "VarItem" = None,
             path: object = None, consulted: object = False) -> "VarItem":
        pass

    def check_folder(self, data_source):
        pass

    def get_folder_str(self) -> str:
        pass

    def get_tree_variable_str(self) -> str:
        pass

    def get_table_variable_str(self) -> str:
        pass


class UdaVarItem(VarItem):
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'UdaVarItem' = None, key='', consulted=False, unit='', description='', data_type='',
                 dimension=''):
        super().__init__(parent, key, unit, description, data_type, dimension)
        self.nested_children = []
        self.consulted = consulted

    def is_folder(self):
        return self.data_type == "folder" or self.data_type == "nested_variable"

    def get_table_variable_str(self) -> str:
        if self.dimension == [1]:
            dimension = ''
        else:
            dimension = '[' + ']['.join('0' for _ in self.dimension) + ']'

        return f'{self.key}{dimension}'

    def get_tree_variable_str(self):
        if self.dimension == [1]:
            dimension = ''
        else:
            dimension = '[' + ']['.join(str(v) for v in self.dimension) + ']'
        return f'{self.key} ({self.unit}) {self.data_type}{dimension}'

    def get_folder_str(self):
        return self.key

    @classmethod
    def load(cls, value: Union[List, Dict], parent: "UdaVarItem" = None,
             path: object = None, consulted: object = False) -> "UdaVarItem":
        if path is None:
            path = []
        if consulted:
            root_item = parent
            root_item.consulted = consulted
        else:
            root_item = UdaVarItem(parent)

        # Stops if value is not a dict, meaning is a variable
        if not isinstance(value, dict):
            return root_item

        # sorts the dict items such that numeric keys come first in ascending order, followed by non-numeric keys in
        # alphabetical order.
        items = sorted(value.items(), key=lambda x: (not x[0].isdigit(), x[0]))

        for key, val in items:
            path.append(key)
            child = cls.load(val, root_item, path)
            child.key = key
            child.path = '-'.join(path)
            if val != '':
                child.data_type = "folder"
            root_item.append_child(child)
            path.pop()

        return root_item

    @staticmethod
    def extract_parts(element):
        parts = re.findall(r'(\d+|\D+)', element)
        return [int(part) if part.isdigit() else part for part in parts]

    @classmethod
    def load_nested_child(cls, value: Union[List, Dict], parent: "UdaVarItem" = None, path: object = None,
                          consulted: object = False) -> "UdaVarItem":
        if path is None:
            path = []
        if consulted:
            root_item = parent
            root_item.consulted = consulted
        else:
            root_item = VarItem(parent)
            root_item.path = f"{parent.path}/{path[-1]}"

        if not isinstance(value, dict):
            return root_item

        sorted_key = sorted(value.keys(), key=cls.extract_parts)
        sorted_value = {key: value[key] for key in sorted_key}
        for key, val in sorted_value.items():
            path.append(key)

            if val.keys() == {'type', 'dimensionality', 'units', 'description'}:
                child = VarItem(root_item)
                child.data_type = val['type']
                child.dimensionality = val['dimensionality']
                child.units = val['units']
                child.description = val['description']
                child.key = f"{root_item.path}/{path[-1]}"
                child.path = key
                child.consulted = True
            else:
                child = cls.load_nested_child(val, root_item, path)
                child.key = key
                child.data_type = "folder"
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

    def check_folder(self, data_source):
        self.consulted = True
        for child in self.children:
            if child.has_child() or child.consulted:
                continue
            data = data_source.get_var_fields(variable=child.key)

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
                child.data_type = 'nested_variable'
                UdaVarItem.load_nested_child(self.group_common_parts(data), child, consulted=True)

                for key, val in data.items():
                    child.append_child(UdaVarItem(parent=child,
                                                  key=f'{child.key}/{key}',
                                                  consulted=True,
                                                  unit=val['units'],
                                                  description=val['description'],
                                                  dimension=val['dimensionality'],
                                                  data_type=val['type']
                                                  ))


class ImasVarItem(VarItem):
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'ImasVarItem' = None, key='', unit='', description='', data_type='', dimension='0'):
        super().__init__(parent, key, unit, description, data_type, dimension)
        self.struct = 0

    def is_folder(self):
        return self.data_type == "structure" or self.data_type == "struct_array"

    def get_tree_variable_str(self):
        return f'{self.key} ({self.data_type})'

    def get_table_variable_str(self):
        begin = ""
        if self.parent and self.parent.key != "":
            begin = self.parent.get_table_variable_str() + "/"
        dimension = '[0' + ",0" * (int(self.dimension) - 1) + "]" if self.dimension != '0' else ''
        struct = '[0]' if self.struct != 0 else ""
        result = begin + self.key + dimension + struct

        return result

    def get_folder_str(self):
        struct = f"(i{self.struct})" if self.struct > 0 else ""
        return f'{self.key}{struct}'

    @classmethod
    def load(cls, value: Union[List, Dict], parent: "ImasVarItem" = None, path: object = None,
             consulted: object = False) -> "ImasVarItem":
        if path is None:
            path = []
        root_item = ImasVarItem(parent)
        if not isinstance(value, dict) or value == {}:
            return root_item

        if 'documentation' in value:
            root_item.description = value['documentation']
        if 'data_type' in value:
            root_item.data_type = value['data_type']
            if value['data_type'] == 'struct_array':
                root_item.struct = parent.struct + 1
        else:
            root_item.data_type = "structure"
        if 'units' in value:
            root_item.unit = value['units']
        if 'dimension' in value:
            root_item.dimension = value['dimension']

        for key, val in value.items():
            if key in ['documentation', 'data_type', 'units', 'dimension']:
                continue
            path.append(key)
            child = cls.load(val, root_item, path)
            child.key = key
            child.path = '/'.join(path)
            root_item.append_child(child)
            path.pop()

        return root_item
