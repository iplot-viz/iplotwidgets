import math
from typing import *

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Signal
from PySide6.QtCore import Qt

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataAccess import DataSource
from iplotDataAccess.dataSourceConfig import DS_CODAC_TYPE, DS_IMAS_TYPE
from iplotWidgets.variableBrowser.tools.converters import parse_pulses


class PulseTableModel(QAbstractTableModel):
    layoutChanged = Signal()

    def __init__(self, data_source: DataSource):
        super(PulseTableModel, self).__init__()
        self.data_source = data_source
        self.dataframe: pd.DataFrame = pd.DataFrame(
            columns=['Pulse', 'Description', 'Status', 'Time From', 'Time To', 'Duration'])
        self._current_page: int = 0
        self._page_size: int = 20

    @property
    def page_size(self) -> int:
        """Return the page size"""
        return self._page_size

    @page_size.setter
    def page_size(self, page_size: int):
        """Set path of the current item"""
        self._page_size = page_size
        self._current_page = 0
        self.layoutChanged.emit()

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = ...) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = index.row() + self._current_page * self._page_size
        col = index.column()
        value = self.dataframe.iloc[row, col]
        if isinstance(value, pd.Timestamp):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(value, pd.Timedelta):
            return self.format_duration(value)

        return value

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return min(self._page_size, len(self.dataframe) - self._current_page * self._page_size)

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = ...) -> int:
        return self.dataframe.shape[1]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])

    def add_row(self, new_values: List) -> None:
        new_dataframe = pd.DataFrame([new_values], columns=self.dataframe.columns)
        self.dataframe = pd.concat([self.dataframe, new_dataframe]).reset_index(drop=True)
        self.layoutChanged.emit()

    def get_pulse(self, row: int):
        return self.dataframe.iloc[row, 0]

    def next_page(self) -> None:
        if self._current_page < self.get_total_pages():
            self._current_page += 1
            self.layoutChanged.emit()

    def previous_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.layoutChanged.emit()

    def get_total_pages(self) -> int:
        rows = self.dataframe.shape[0]
        return math.ceil(rows / self._page_size)

    def get_real_page(self) -> int:
        if self.get_total_pages() > 0:
            return self._current_page + 1
        else:
            return 0

    def load(self) -> None:
        """ Load model from zero """
        document = AppDataAccess.da.get_pulse_list(data_source_name=self.data_source.name)

        if self.data_source.dtype == DS_CODAC_TYPE:
            document = parse_pulses(document)

        self.load_document(document)

    def load_document(self, document: dict) -> None:
        """Load model from a dictionary
        """
        self.beginResetModel()

        if self.data_source.dtype == DS_IMAS_TYPE:
            for key, value in document.items():
                self.add_row([ImasPulseItem(key, value)])

        elif self.data_source.dtype == DS_CODAC_TYPE:
            # Clear previous dataframe if existed
            self.dataframe.drop(self.dataframe.index, inplace=True)
            for key, value in document.items():
                self.add_row(
                    [key, value['description'], value['status'], value['timeFrom'], value['timeTo'], value['duration']])

        self.endResetModel()

    @staticmethod
    def format_duration(duration: pd.Timedelta) -> str:
        total_seconds = int(duration.total_seconds())
        days, seconds = divmod(total_seconds, 86400)  # 86400 seconds in a day
        years, days = divmod(days, 365)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        microseconds = duration.microseconds
        nanoseconds = duration.nanoseconds

        time_str = f"{hours:02}:{minutes:02}:{seconds:02}.{microseconds:06}{nanoseconds:03}"

        if years > 0:
            return f"{years} year{'s' if years > 1 else ''} {days} days {time_str}"
        elif days == 0:
            return f"{time_str}"
        else:
            return f"{days} days {time_str}"


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
