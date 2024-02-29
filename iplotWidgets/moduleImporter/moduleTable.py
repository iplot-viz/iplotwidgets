import pandas as pd
from PySide6.QtGui import QColor
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView, QStyledItemDelegate
from PySide6.QtCore import Qt, Signal

from typing import *


class ModuleTable(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setColumnWidth(0, 100)
        self.model = ModuleTableModel()
        self.setModel(self.model)
        self.setItemDelegate(CustomItemDelegate())

    def remove_selected_module(self, rows) -> List[int]:
        self.model.remove_row(rows)
        self.clearSelection()
        return rows

    def clear_table(self, num):
        self.model.clear_model(num)

    def get_variables_df(self) -> pd.DataFrame:
        return self.model.dataframe

    def get_variables_list(self) -> List[str]:
        return self.model.get_model_list()


class CustomItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)

        # Change background color for the first n rows of the table
        if index.row() < option.widget.model.total_default_modules:
            option.backgroundBrush = QColor(200, 200, 200)  # Gray background


class ModuleTableModel(QAbstractTableModel):
    layoutChanged = Signal()

    def __init__(self):
        super(ModuleTableModel, self).__init__()
        self._dataframe = pd.DataFrame(columns=['Module'])
        self._total_default_modules = 0

    @property
    def dataframe(self) -> pd.DataFrame:
        """Return the data"""
        return self._dataframe

    @dataframe.setter
    def dataframe(self, dataframe: pd.DataFrame):
        """Set path of the current item"""
        self._dataframe = dataframe

    @property
    def total_default_modules(self) -> int:
        """Return number of default modules"""
        return self._total_default_modules

    @total_default_modules.setter
    def total_default_modules(self, total_default_modules: int):
        """Set number of default modules"""
        self._total_default_modules = total_default_modules

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.dataframe.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return self.dataframe.shape[0]

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return 1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])

    def add_row(self, new_values: List):
        new_dataframe = pd.DataFrame([new_values], columns=['Module'])
        self.dataframe = pd.concat([self.dataframe, new_dataframe]).reset_index(drop=True)
        self.layoutChanged.emit()

    def remove_row(self, selected_module):
        self.dataframe.drop(selected_module, inplace=True)
        self.dataframe.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()

    def clear_model(self, num):
        self.dataframe = self.dataframe.head(num)
        self.layoutChanged.emit()

    def get_model_list(self) -> List[str]:
        return self.dataframe['Module'].values.tolist()
