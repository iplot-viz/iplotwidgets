from typing import Any, List, Dict, Union
from PySide6 import QtGui
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QSize, QPersistentModelIndex
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataAccess import DataSource
from iplotDataAccess.dataSourceConfig import DS_CODAC_TYPE, DS_IMAS_TYPE
from iplotWidgets.variableBrowser.tools.converters import parse_pulses_to_dict


class PulseModel(QAbstractItemModel):
    """ An editable model of Json data """

    def __init__(self, data_source: DataSource, parent: QObject = None, search=False):
        super().__init__(parent)

        self.root_item = PulseItem()
        self.data_source = data_source
        self.search: bool = search
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
        """ Load model from zero """

        document = AppDataAccess.da.get_pulse_list(data_source_name=self.data_source.name)

        if self.data_source.dtype == DS_CODAC_TYPE:
            document = parse_pulses_to_dict(document)

        self.load_document(document)

    def load_document(self, document: dict):
        """Load model from a dictionary
        """

        self.beginResetModel()

        if self.data_source.dtype == DS_IMAS_TYPE:
            self.root_item = ImasPulseItem.load(document)
        elif self.data_source.dtype == DS_CODAC_TYPE:
            self.root_item = UdaPulseItem.load(document, UdaPulseItem(data_type="folder"), consulted=True)

        self.endResetModel()

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        """Override from QAbstractItemModel

        Return data from a json item according index and role

        """
        if not index.isValid():
            return None

        item = index.internalPointer()  # type: PulseItem

        if role == Qt.DisplayRole:
            if item.is_folder():
                return item.get_folder_str()
            else:
                return item.get_tree_variable_str()
        elif role == Qt.EditRole:
            if index.column() == 1:
                return item.key
        elif role == Qt.SizeHintRole:
            "giving size hint"
            return QSize(1000, 20)
        elif role == Qt.DecorationRole:
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


class PulseItem:
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: 'PulseItem' = None, key='', description='', data_type=''):
        self.parent = parent
        self.key = key
        self.path = ''
        self.description = description
        self.data_type = data_type
        self.children = []

    def is_folder(self) -> bool:
        pass

    def append_child(self, item: "PulseItem"):
        """Add item as a child"""
        self.children.append(item)

    def child(self, row: int) -> "PulseItem":
        """Return the child of the current item from the given row"""
        return self.children[row]

    def has_child(self) -> bool:
        """Return if the current item has children or not"""
        return bool(self.children)

    def parent(self) -> "PulseItem":
        """Return the parent of the current item"""
        return self.parent

    def child_count(self) -> int:
        """Return the number of children of the current item"""
        return len(self.children)

    def row(self) -> int:
        """Return the row where the current item occupies in the parent"""
        return self.parent.children.index(self) if self.parent else 0

    def load(self, value: Union[List, Dict], parent: "PulseItem" = None,
             path: object = None, consulted: object = False) -> "PulseItem":
        pass

    def check_folder(self, data_source):
        pass

    def get_folder_str(self) -> str:
        pass

    def get_tree_variable_str(self) -> str:
        pass

    def get_table_variable_str(self) -> str:
        pass


class UdaPulseItem(PulseItem):
    """A Json item corresponding to a pulse in QTreeView"""

    def __init__(self, parent: 'UdaPulseItem' = None, key='', consulted=False, description='', pulse_id='',
                 status='', time_from=None, time_to=None, duration=None, data_type=''):
        super().__init__(parent, key, description, data_type)
        self.pulse_id = pulse_id
        self.status = status
        self.timeFrom = time_from
        self.timeTo = time_to
        self.duration = duration
        self.consulted = consulted

    def is_folder(self):
        return self.data_type == "folder"

    def get_tree_variable_str(self):
        return f'{self.key}'

    def get_folder_str(self):
        return self.key

    @classmethod
    def load(cls, value: Union[List, Dict], parent: "UdaPulseItem" = None, path: object = None,
             consulted: object = False) -> "UdaPulseItem":
        if path is None:
            path = []
        if consulted:
            root_item = parent
            root_item.consulted = consulted
        else:
            root_item = UdaPulseItem(parent)

        if list(value.keys()) == ['description', 'status', 'timeFrom', 'timeTo', 'duration']:
            root_item.description = value['description']
            root_item.status = value['status']
            root_item.timeFrom = value['timeFrom']
            root_item.timeTo = value['timeTo']
            root_item.duration = value['duration']
            return root_item

        items = sorted(value.items(), key=lambda x: (not x[0].isdigit(), x[0]))

        for key, val in items:
            path.append(key)
            child = cls.load(val, root_item, path)
            if list(val.keys()) == ['description', 'status', 'timeFrom', 'timeTo', 'duration']:
                child.key = key
                child.data_type = "pulse"
            else:
                child.key = key
                child.data_type = "folder"
            child.path = '-'.join(path)
            root_item.append_child(child)
            path.pop()

        return root_item


class ImasPulseItem(PulseItem):
    """A Json item corresponding to a pulse in QTreeView"""

    def __init__(self, parent: 'ImasPulseItem' = None, key='', description='', pulse_id='', status='',
                 time_from=None, time_to=None, data_type=''):
        super().__init__(parent, key, description, data_type)
        self.pulse_id = pulse_id
        self.status = status
        self.timeFrom = time_from
        self.timeTo = time_to
