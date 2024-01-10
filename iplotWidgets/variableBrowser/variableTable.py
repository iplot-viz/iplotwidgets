import pandas as pd
from PySide6.QtGui import QStandardItemModel
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt
from typing import *


class TableModel(QAbstractTableModel):

    def __init__(self):
        super(TableModel, self).__init__()
        self._dataframe = pd.DataFrame(columns=['DS', 'Variable'])

    @property
    def dataframe(self) -> pd.DataFrame:
        """Return the data"""
        return self._dataframe

    @dataframe.setter
    def dataframe(self, dataframe: pd.DataFrame):
        """Set path of the current item"""
        self._dataframe = dataframe

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.dataframe.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return self.dataframe.shape[0]

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return 2

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])

    def add_row(self, new_values: List):
        new_dataframe = pd.DataFrame([new_values], columns=['DS', 'Variable'])
        self.dataframe = pd.concat([self.dataframe, new_dataframe])
        self.layoutChanged.emit()

    def clear_model(self):
        self.dataframe = pd.DataFrame(columns=['DS', 'Variable'])
        self.layoutChanged.emit()

    def get_model_list(self):
        return self.dataframe.values.tolist()


class VariableTable(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.model_table = QStandardItemModel()
        self.setModel(self.model_table)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setColumnWidth(0, 100)
        self.model = TableModel()
        self.setModel(self.model)

        print()

    def remove_from_table(self):
        index = self.selectedIndexes()
        rows = [ix.row() for ix in index]
        for row in reversed(rows):
            self.model_table.removeRow(row)
        self.clearSelection()

    def clear_table(self):
        self.model.clear_model()

    def get_variables_df(self) -> pd.DataFrame:
        return self.model.dataframe

    def get_variables_list(self):
        return self.model.get_model_list()


class ModuleTableModel(QAbstractTableModel):

    def __init__(self, ):
        super(ModuleTableModel, self).__init__()
        self._dataframe = pd.DataFrame(columns=['Module'])

    @property
    def dataframe(self) -> pd.DataFrame:
        """Return the data"""
        return self._dataframe

    @dataframe.setter
    def dataframe(self, dataframe: pd.DataFrame):
        """Set path of the current item"""
        self._dataframe = dataframe

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

    def remove_row(self, selectedModule):
        # Check
        selectedModule = [i for i in selectedModule if i > 3]
        self.dataframe.drop(selectedModule, inplace=True)
        self.dataframe.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()

    def clear_model(self):
        self.dataframe = self.dataframe.head(4)
        self.layoutChanged.emit()

    def get_model_list(self):
        return self.dataframe['Module'].values.tolist()

class ModuleTable(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.model_table = QStandardItemModel()
        self.setModel(self.model_table)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setColumnWidth(0, 100)
        self.model = ModuleTableModel()
        self.setModel(self.model)

        print()

    def remove_from_table(self):
        index = self.selectedIndexes()
        rows = [ix.row() for ix in index]
        for row in reversed(rows):
            self.model_table.removeRow(row)
        self.clearSelection()

    def remove_selected_module(self):
        index = self.selectedIndexes()
        rows = [ix.row() for ix in index]
        self.model.remove_row(rows)
        self.clearSelection()
        return rows

    def clear_table(self):
        self.model.clear_model()

    def get_variables_df(self) -> pd.DataFrame:
        return self.model.dataframe

    def get_variables_list(self):
        return self.model.get_model_list()