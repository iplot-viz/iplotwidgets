from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QHeaderView,
    QStyle, QStyleOptionViewItem, QStyledItemDelegate, QTableView,
)

from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataSource import DS_IMASPY_TYPE
from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel
from iplotWidgets.sizing import FontScaledView

_LINK_COLOR = QColor(30, 100, 200)
_DASHBOARD_LINK_COL = "dashboard_link"
_UUID_COL = "uuid"


class _LinkDelegate(QStyledItemDelegate):
    """Renders a table cell as a blue underlined hyperlink when a URL is present."""

    def paint(self, painter, option, index):
        url = index.data(Qt.ItemDataRole.UserRole)
        if not (url and isinstance(url, str)):
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        style = opt.widget.style() if opt.widget else QApplication.style()

        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, opt.widget)

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        painter.save()
        painter.setPen(_LINK_COLOR)
        font = painter.font()
        font.setUnderline(True)
        painter.setFont(font)
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )
        painter.restore()


class PulseTable(FontScaledView, QTableView):
    COLUMN_WIDTHS = {0: 100}

    def __init__(self):
        QTableView.__init__(self)
        self.setSelectionMode(self.selectionMode().ExtendedSelection)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.apply_font_metrics()

        self.models = {'SEARCH': PulseTableModel(data_source=AppDataAccess.da.default_ds)}
        self.current_model_name = ''

        self._link_delegate = _LinkDelegate(self)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clicked.connect(self._on_cell_clicked)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(True)

        self.load_model(AppDataAccess.da.default_ds)

        self.adjust_columns(AppDataAccess.da.default_ds)

    def _is_imaspy(self):
        model = self.models.get(self.current_model_name)
        return model is not None and model.data_source.source_type == DS_IMASPY_TYPE
    
    def _apply_imaspy_column_settings(self):
        """Hide the dashboard_link column and attach link delegate to uuid."""
        if not self._is_imaspy():
            return
        df = self.get_current_model().dataframe
        if df is None or df.empty:
            return
        cols = list(df.columns)

        self.setColumnHidden(cols.index(_DASHBOARD_LINK_COL), True)
        self.setItemDelegateForColumn(cols.index(_UUID_COL), self._link_delegate)

    def _on_cell_clicked(self, index):
        """ Open URL in browser when clicked """
        if not index.isValid() or not self._is_imaspy():
            return
        if self.get_current_model().dataframe.columns[index.column()] == _UUID_COL:
            url = index.data(Qt.ItemDataRole.UserRole)
            QDesktopServices.openUrl(QUrl(url))

    def mouseMoveEvent(self, event):
        """ Change cursor to pointing hand if hovering over a UUID link in IMASPY data source """
        if self._is_imaspy():
            index = self.indexAt(event.pos())
            if index.isValid() and self.get_current_model().dataframe.columns[index.column()] == _UUID_COL:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().mouseMoveEvent(event)

    def adjust_columns(self, data_source):
        model_df = self.models[data_source.name].dataframe
        for column in range(model_df.shape[1]):
            if not self.isColumnHidden(column):
                self.resizeColumnToContents(column)

    def load_model(self, data_source):
        ds_name = data_source.name
        if ds_name not in self.models:
            self.models[ds_name] = PulseTableModel(data_source=data_source)
            self.models[ds_name].load()

        self.current_model_name = ds_name
        self.setModel(self.models[ds_name])
        if data_source.source_type == DS_IMASPY_TYPE:
            self._apply_imaspy_column_settings()

    def set_model(self, ds_name):
        if ds_name in self.models:
            self.current_model_name = ds_name
            self.setModel(self.models[ds_name])
            model = self.models[ds_name]
            if model.data_source.source_type == DS_IMASPY_TYPE:
                self._apply_imaspy_column_settings()

    def get_current_model(self) -> PulseTableModel:
        return self.models[self.current_model_name]

    def get_page_size(self):
        return self.get_current_model().page_size

    def get_total_pages(self):
        return self.get_current_model().get_total_pages()

    def get_current_page(self):
        return self.get_current_model().get_real_page()

    def get_pulse_info(self, row):
        self.get_current_model().get_pulse_info(row)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection_to_clipboard()
            return
        super().keyPressEvent(event)

    def _copy_selection_to_clipboard(self):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        rows = sorted({idx.row() for idx in indexes})
        cols = sorted({idx.column() for idx in indexes})
        model = self.model()
        lines = []
        if len(cols) > 1:
            headers = [str(model.headerData(c, Qt.Orientation.Horizontal,
                                            Qt.ItemDataRole.DisplayRole) or '')
                       for c in cols]
            lines.append('\t'.join(headers))
        for row in rows:
            values = []
            for col in cols:
                value = model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole)
                values.append('' if value is None else str(value))
            lines.append('\t'.join(values))
        QApplication.clipboard().setText('\n'.join(lines))
