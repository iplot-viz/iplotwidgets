from typing import *

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Signal
from PySide6.QtCore import Qt

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataSourceConfig import DS_CODAC_TYPE, DS_IMAS_TYPE
from iplotWidgets.variableBrowser.tools.converters import parse_pulses


class PulseTableModel(QAbstractTableModel):
    layoutChanged = Signal()

    def __init__(self):
        super(PulseTableModel, self).__init__()
        self._dataframe = pd.DataFrame(columns=['Pulse'])
        self._current_dataframe = pd.DataFrame(columns=['Pulse'])

    @property
    def dataframe(self) -> pd.DataFrame:
        """Return the data"""
        return self._dataframe

    @property
    def current_dataframe(self) -> pd.DataFrame:
        """Return the data inside the current page"""
        return self._current_dataframe

    @dataframe.setter
    def dataframe(self, dataframe: pd.DataFrame):
        """Set path of the current item"""
        self._dataframe = dataframe

    @current_dataframe.setter
    def current_dataframe(self, dataframe: pd.DataFrame):
        """Set path of the current item"""
        self._current_dataframe = dataframe

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.current_dataframe.iloc[index.row(), index.column()].key
            return value

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return self.current_dataframe.shape[0]

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return 1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])

    def add_row(self, new_values: List):
        new_dataframe = pd.DataFrame([new_values], columns=['Pulse'])
        self.dataframe = pd.concat([self.dataframe, new_dataframe]).reset_index(drop=True)
        self.layoutChanged.emit()

    def get_pulse(self, index: int):
        return self.current_dataframe.iloc[index, 0]

    def paginate_dataframe(self, page_size, page_num):
        """ Pagination implementation """
        offset = page_size * (page_num - 1)
        self.current_dataframe = self.dataframe[offset:offset + page_size]
        self.layoutChanged.emit()

    def load(self, data_source, page_size, page_num):
        """ Load model from zero """
        document = AppDataAccess.da.get_pulse_list(data_source_name=data_source.name)

        if data_source.dtype == DS_CODAC_TYPE:
            document = parse_pulses(document)

        self.load_document(document, data_source, page_size, page_num)

    def load_document(self, document: dict, data_source, page_size, page_num):
        """Load model from a dictionary
        """
        self.beginResetModel()

        if data_source.dtype == DS_IMAS_TYPE:
            for key, value in document.items():
                self.add_row([ImasPulseItem(key, value)])

        elif data_source.dtype == DS_CODAC_TYPE:
            # Clear previous dataframe if existed
            self.dataframe.drop(self.dataframe.index, inplace=True)
            for key, value in document.items():
                self.add_row([UdaPulseItem(key, value)])

        # Pagination
        self.paginate_dataframe(page_size, page_num)

        self.endResetModel()


class UdaPulseItem:
    def __init__(self, key='', info: dict = None):
        self.key = key
        self.description = info['description']
        self.status = info['status']
        self.timeFrom = info['timeFrom']
        self.timeTo = info['timeTo']
        self.duration = info['duration']


class ImasPulseItem:
    def __init__(self, key='', info: dict = None):
        self.key = key
        self.description = info['description']
        self.status = info['status']
        self.timeFrom = info['timeFrom']
        self.timeTo = info['timeTo']
        self.duration = info['duration']
