import math

from typing import Any, Union, List

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Signal
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from pandas.core.interchange.dataframe_protocol import DataFrame
from iplotLogging import setupLogger as setupLog
from iplotDataAccess.dataSource import DataSource, DS_IMASPY_TYPE

logger = setupLog.get_logger(__name__)

# Leading column flagging the pulses the caller already uses; the model
# adds it in front of whatever columns the data source returns.
SELECTED_COL = 'Selected'


class PulseTableModel(QAbstractTableModel):
    layoutChanged = Signal()


    def __init__(self, data_source: DataSource):
        super(PulseTableModel, self).__init__()
        self.data_source = data_source
        if self.data_source.source_type == DS_IMASPY_TYPE:
            self._loaded = False
            self._document: pd.DataFrame = pd.DataFrame()

        self.dataframe: pd.DataFrame = pd.DataFrame()
        self.selected_pulses: set = set()
        self._selected_background = QBrush(QColor(255, 244, 200))

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
        if not index.isValid():
            return None
        row = index.row() + self._current_page * self._page_size
        col = index.column()
        col_name = self.dataframe.columns[col]

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.dataframe.iloc[row, col]
            if col_name == SELECTED_COL:
                return '✓' if value else ''
            if isinstance(value, pd.Timestamp):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(value, pd.Timedelta):
                return self.format_duration(value)
            return value
        if role == Qt.ItemDataRole.BackgroundRole and self._is_selected(row):
            return self._selected_background
        if self.data_source.source_type == DS_IMASPY_TYPE:
            if role == Qt.ItemDataRole.UserRole:
                if col_name == "uuid":
                    link = self.dataframe.at[self.dataframe.index[row], "dashboard_link"]
                    if pd.notna(link) and isinstance(link, str) and link:
                        return link

        return None

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
        return self._pulse_at(row + self._current_page * self._page_size)

    def _pulse_at(self, current_row: int):
        if self.data_source.source_type == DS_IMASPY_TYPE:
            if "imas_uri" in self.dataframe.columns:
                # Append cache_mode=none for UDA URIs
                val = self.dataframe.at[self.dataframe.index[current_row], "imas_uri"]
                if pd.notna(val) and isinstance(val, str):
                    val_lower = val.lower()
                    if "uda" in val_lower and "cache_mode=none" not in val:
                        sep = "&" if "?" in val else "?"
                        val = f"{val}{sep}cache_mode=none"
                return val
            else:
                return self.dataframe.iloc[current_row, self._data_col(0)]
        else:
            return self.dataframe.iloc[current_row, self._data_col(0)]

    def _data_col(self, position: int) -> int:
        # Source columns keep their relative order behind the Selected one.
        return position + 1 if SELECTED_COL in self.dataframe.columns else position

    def _is_selected(self, row: int) -> bool:
        return SELECTED_COL in self.dataframe.columns and bool(self.dataframe[SELECTED_COL].iat[row])

    def _time_column(self):
        for col in self.dataframe.columns:
            if pd.api.types.is_datetime64_any_dtype(self.dataframe[col]):
                return col
        return None

    def set_selected_pulses(self, pulses) -> None:
        """Flag the given pulse identifiers (as returned by ``get_pulse``)."""
        self.selected_pulses = {str(p).strip() for p in pulses if str(p).strip()}
        if self.dataframe.empty:
            return
        self._refresh_selected_column()
        rows = self.rowCount()
        if rows > 0:
            self.dataChanged.emit(self.index(0, 0), self.index(rows - 1, self.columnCount() - 1))

    def _refresh_selected_column(self) -> None:
        if not [c for c in self.dataframe.columns if c != SELECTED_COL]:
            return
        flags = [str(self._pulse_at(i)) in self.selected_pulses for i in range(len(self.dataframe))]
        if SELECTED_COL in self.dataframe.columns:
            self.dataframe[SELECTED_COL] = flags
        else:
            self.dataframe.insert(0, SELECTED_COL, flags)

    def next_page(self) -> None:
        # _current_page is 0-indexed; valid range is [0, total_pages - 1].
        if self._current_page < self.get_total_pages() - 1:
            self._current_page += 1
            self.layoutChanged.emit()

    def previous_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.layoutChanged.emit()

    def go_to_page(self, page: int) -> None:
        """Jump to the 1-indexed ``page``; out-of-range targets are ignored."""
        if 1 <= page <= self.get_total_pages() and page - 1 != self._current_page:
            self._current_page = page - 1
            self.layoutChanged.emit()

    @staticmethod
    def page_links(current: int, total: int) -> list:
        """Pages worth a direct link around the 1-indexed ``current`` one.

        The first and last pages plus a window of two on each side of the
        current one, in order, with ``None`` standing for the pages skipped
        between them: ``[1, None, 3, 4, 5, 6, 7, None, 100]``.
        """
        if total < 1:
            return []
        wanted = {1, total} | {p for p in range(current - 2, current + 3) if 1 <= p <= total}
        links = []
        for page in sorted(wanted):
            if links and page != links[-1] + 1:
                links.append(None)
            links.append(page)
        return links

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

   
    def load(self) -> None:
        """
        Load (or reload) the pulses DataFrame.
        Disk caching with TTL is handled inside get_pulses_df().
        """
        if self.data_source.source_type == DS_IMASPY_TYPE:
            if self._loaded:
                return
            df = self.data_source.get_pulses_df()

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

        time_col = self._time_column()
        if time_col is not None:
            self.dataframe = self.dataframe.sort_values(
                by=time_col, ascending=False, ignore_index=True)
        self._refresh_selected_column()

        self.endResetModel()

    def get_pulse_info(self, row):
        current_row = row + self._current_page * self._page_size
        if self.data_source.source_type == DS_IMASPY_TYPE:
            uuid_val = None
            if "uuid" in self.dataframe.columns:
                uuid_val = str(self.dataframe.at[self.dataframe.index[current_row], "uuid"])

            info = self.data_source.get_pulse_info(uuid=uuid_val)
            logger.info("====================================================")
            logger.info(f"uuid = {uuid_val}")
            logger.info("====================================================")
            logger.info(info)
            logger.info("====================================================")
        else:
            pulse = int(self.dataframe.iloc[current_row, self._data_col(0)])
            run = int(self.dataframe.iloc[current_row, self._data_col(1)])
            info = self.data_source.get_pulse_info(pulse=pulse, run=run)
            logger.info("====================================================")
            logger.info(f"pulse = {pulse} run={run}")
            logger.info("====================================================")
            logger.info(info)
            logger.info("====================================================")

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

        if col_name == SELECTED_COL:
            # Selected pulses grouped together, the rest most recent first.
            keys, orders = [SELECTED_COL], [ascending]
            time_col = self._time_column()
            if time_col is not None:
                keys.append(time_col)
                orders.append(False)
            self.dataframe.sort_values(by=keys, ascending=orders, inplace=True, ignore_index=True)
            self.layoutChanged.emit()
            return

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
