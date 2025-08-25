import math
import os
from pathlib import Path
import pickle
from datetime import datetime, timedelta
from typing import Any, Union, List

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Signal
from PySide6.QtCore import Qt
from pandas.core.interchange.dataframe_protocol import DataFrame
from iplotLogging import setupLogger as setupLog
from iplotDataAccess.dataSource import DataSource, DS_IMASPY_TYPE

logger = setupLog.get_logger(__name__)

class PulseTableModel(QAbstractTableModel):
    layoutChanged = Signal()
    
    CACHE_TTL = timedelta(days=3) 

    def __init__(self, data_source: DataSource):
        super(PulseTableModel, self).__init__()
        self.data_source = data_source
        if self.data_source.source_type == DS_IMASPY_TYPE:
            cache_dir = os.environ.get('IPLOT_DUMP_PATH', f"{Path.home()}/.local/1Dtool/cache")
            os.makedirs(cache_dir, exist_ok=True)
            self.CACHE_FILE = os.path.join(cache_dir, "pulses_df.pkl")
            self._loaded = False
            self._document: pd.DataFrame = pd.DataFrame()
        
        self.dataframe: pd.DataFrame = pd.DataFrame()

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
        if not new_dataframe.empty and not new_dataframe.isna().all().all():
            self.dataframe = pd.concat([self.dataframe, new_dataframe]).reset_index(drop=True)
        self.layoutChanged.emit()

    def get_pulse(self, row: int):
        current_row = row + self._current_page * self._page_size
        if self.data_source.source_type == DS_IMASPY_TYPE:
            run = int(self.dataframe.iloc[current_row, 1])
            return self.dataframe.iloc[current_row, 0] + '/' + str(run)
        else:
            return self.dataframe.iloc[current_row, 0]

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

    @property
    def document(self) -> pd.DataFrame:
        """Access the underlying DataFrame, triggering load() if needed."""
        if not self._loaded:
            self.load()
        return self._document

    def _cache_is_valid(self) -> bool:
        """True if cache exists and is newer than TTL."""
        if not os.path.exists(self.CACHE_FILE):
            return False
        mtime = datetime.fromtimestamp(os.path.getmtime(self.CACHE_FILE))
        return (datetime.now() - mtime) < self.CACHE_TTL
    
    def load(self) -> None:
        """
        Load (or reload) the pulses DataFrame, using disk-cache with TTL.
        Subsequent calls before TTL expires are<<1 s; after TTL, will re-fetch.
        """
        if self.data_source.source_type == DS_IMASPY_TYPE:
            if self._loaded:
                return

            if self._cache_is_valid():
                # fast load from disk
                with open(self.CACHE_FILE, "rb") as f:
                    df = pickle.load(f)
            else:
                df = self.data_source.get_pulses_df()    # ~20 s
                with open(self.CACHE_FILE, "wb") as f:
                    pickle.dump(df, f)

            # finally, update the model
            self._document = df
            self.load_document(df)
            self._loaded = True
        else:
            document = self.data_source.get_pulses_df()

            self.load_document(document)

    def load_document(self, new_df: DataFrame) -> None:
        """Load model from a dictionary
        """
        self.beginResetModel()

        # Clear previous dataframe if existed
        self.dataframe = new_df

        self.endResetModel()

    def get_pulse_info(self, row):
        pulse = int(self.dataframe.iloc[row, 0])
        run = int(self.dataframe.iloc[row, 1])
        info = self.data_source.get_pulse_info(pulse=pulse, run=run)
        print("====================================================")
        print(f"pulse = {pulse} run={run}")
        print("====================================================")
        print(info)
        print("====================================================")

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

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """
        Sort the model by the given column index and order.
        Numeric strings sorted numerically, others lexicographically.
        """
        col_name = self.dataframe.columns[column]
        ascending = (order == Qt.SortOrder.AscendingOrder)

        self.layoutAboutToBeChanged.emit()

        # Vectorized numeric conversion: will be NaN if not numeric
        numeric_key = pd.to_numeric(self.dataframe[col_name], errors='coerce')

        # If there are any valid numbers, sort numerically; else, sort as string
        if numeric_key.notna().any():
            self.dataframe['_sort_key'] = numeric_key
        else:
            self.dataframe['_sort_key'] = self.dataframe[col_name].astype(str)

        self.dataframe.sort_values(
            by=['_sort_key'],
            ascending=[ascending],
            inplace=True,
            ignore_index=True
        )
        self.dataframe.drop(columns=['_sort_key'], inplace=True)

        self.layoutChanged.emit()
