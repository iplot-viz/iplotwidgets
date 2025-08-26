import time

import pandas as pd
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, \
    QProgressBar, QLabel
from PySide6.QtCore import Qt, Signal

from iplotDataAccess.dataAccess import DataSource
from iplotWidgets.pulseBrowser.PulseTable import PulseTable
from iplotLogging import setupLogger as setupLog
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotDataAccess.dataSource import DS_IMASPY_TYPE

logger = setupLog.get_logger(__name__)


class PulseBrowser(QWidget):
    cmd_finish = Signal(object)
    srch_finish = Signal(object)
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(PulseBrowser, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, *args, **kwargs):
        if not self._initialized:
            self._initialized = True
            super().__init__(*args, **kwargs)

            self.resize(1300, 730)
            self.width = 840
            self.height = 680
            self.setAcceptDrops(True)
            self.setGeometry(
                QStyle.alignedRect(
                    Qt.LayoutDirection.LeftToRight,
                    Qt.AlignmentFlag.AlignCenter,
                    self.size(),
                    QGuiApplication.primaryScreen().availableGeometry(),
                ),
            )
            self.setWindowTitle("Pulse search")
            self.flag = ""
            self.table = PulseTable()
            self.table.setSortingEnabled(True)
            self.table.doubleClicked.connect(self.info_pulse)
            self.searchbar = QLineEdit()
            self.searchbar.textChanged.connect(self.update_display)
            self.searchbar.returnPressed.connect(self.search)

            self.path_input = QLineEdit()
            self.add_to_mint_btn = QPushButton('Add to MINT')
            self.add_to_mint_btn.clicked.connect(self.add_pulse)

            self.search_btn = QPushButton('Search')
            self.search_btn.clicked.connect(self.search)
            self.refresh_btn = QPushButton('Refresh')
            self.refresh_btn.clicked.connect(self.refresh)

            self.previous_page = QPushButton('<')
            self.previous_page.clicked.connect(self.previous_pulses)
            self.next_page = QPushButton('>')
            self.next_page.clicked.connect(self.next_pulses)

            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setParent(self)
            self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.hide()

            self.data_sources = AppDataAccess.da.get_connected_data_sources()
            self.sources_combo = QComboBox()
            for ds in self.data_sources:
                self.sources_combo.addItem(ds.name, userData=ds)
            self.sources_combo.setCurrentText(AppDataAccess.da.get_default_ds_name())
            self.sources_combo.currentTextChanged.connect(self.change_model)

            top_h_layout = QHBoxLayout()
            top_h_layout.addWidget(self.sources_combo)
            top_h_layout.addWidget(self.refresh_btn)
            top_h_layout.addWidget(self.searchbar)
            top_h_layout.addWidget(self.search_btn)
            top_v_layout = QVBoxLayout()
            top_v_layout.addLayout(top_h_layout)
            top_v_layout.addWidget(self.progress_bar)

            bot_v_layout = QVBoxLayout()
            bot_v_layout.addWidget(self.add_to_mint_btn)

            # Pagination
            pagination_layout = QHBoxLayout()
            self.rows_text = QLabel("Rows per page:")
            self.rows_page = QComboBox()
            self.rows_page.addItems(["20", "50", "100"])
            self.rows_page.setCurrentText("20")
            self.rows_page.currentIndexChanged.connect(self.update_page_size)
            self.page_label = QLabel()
            self.update_page_label()

            pagination_layout.addWidget(self.rows_text)
            pagination_layout.addWidget(self.rows_page)
            pagination_layout.addStretch()
            pagination_layout.addWidget(self.page_label)
            pagination_layout.addWidget(self.previous_page)
            pagination_layout.addWidget(self.next_page)

            mid_v_layout = QVBoxLayout()
            mid_v_layout.addWidget(self.table)
            mid_v_layout.addLayout(pagination_layout)

            main_v_layout = QVBoxLayout()
            main_v_layout.addLayout(top_v_layout)
            main_v_layout.addLayout(mid_v_layout)
            main_v_layout.addLayout(bot_v_layout)
            self.setLayout(main_v_layout)

    def get_current_source(self) -> DataSource:
        return self.sources_combo.currentData()

    def change_model(self):
        new_source = self.get_current_source()
        # self.table.reset_page()
        self.table.load_model(new_source)
        self.table.adjust_columns(new_source)
        self.update_page_size()
        self.update_page_label()

    def update_display(self):
        text = self.searchbar.text()
        if not len(text):
            self.table.set_model(self.get_current_source().name)
            self.update_page_label()

    def update_page_label(self):
        self.page_label.setText(f"Page {self.table.get_current_page()} of {self.table.get_total_pages()}")
        self.update_pagination_buttons()

    def update_pagination_buttons(self):
        total_pages = self.table.get_total_pages()
        self.previous_page.setEnabled(self.table.get_current_page() > 1 and total_pages > 0)
        self.next_page.setEnabled(self.table.get_current_page() < total_pages and total_pages > 0)

    def previous_pulses(self):
        model = self.table.get_current_model()
        model.previous_page()
        self.update_page_label()
        self.table.resizeColumnsToContents()

    def next_pulses(self):
        model = self.table.get_current_model()
        model.next_page()
        self.update_page_label()
        self.table.resizeColumnsToContents()

    def update_page_size(self):
        self.table.get_current_model().page_size = self.get_page_size()
        self.update_page_label()

    def get_page_size(self):
        return int(self.rows_page.currentText())

    def add_pulse(self):
        indexes = self.table.selectedIndexes()
        pulses = []
        rows = list({ix.row() for ix in indexes})

        for row in rows:
            value = self.table.models[self.table.current_model_name].get_pulse(row)
            pulses.append(value)

        # Check implemented to insert the pulses in the correct place
        if self.flag == "table":
            self.cmd_finish.emit(pulses)
        elif self.flag == "button":
            self.srch_finish.emit(pulses)
        self.table.clearSelection()

    def search(self):
        text = self.searchbar.text()
        if text == '':
            return
        self.search_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setFormat("Retrieving the variable list from the server")
        self.progress_bar.setValue(40)
        time.sleep(0.4)

        data_source = self.get_current_source()
        found = data_source.search_pulses_df(text)
        columns = found.columns
        search_model = self.table.models['SEARCH']
        # If the type of data source has changed and a search is made, the SEARCH MODEL dataframe must be updated
        if len(search_model.dataframe.columns) > len(columns):
            search_model.dataframe = pd.DataFrame(columns=columns)
        elif len(search_model.dataframe.columns) < len(columns):
            search_model.dataframe = pd.DataFrame(columns=columns)

        search_model.data_source = data_source
        self.table.set_model('SEARCH')

        if not found.empty:
            self.progress_bar.setFormat("Loading pulses into the model")
            self.progress_bar.setValue(80)
            search_model.load_document(found)
            self.update_page_size()
            time.sleep(0.4)
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
            self.progress_bar.setFormat("Empty model")
            self.progress_bar.setValue(80)
            self.progress_bar.setStyleSheet("")
            search_model.load_document(found)
            time.sleep(2)

        self.update_page_label()

        # Search done
        self.search_btn.setEnabled(True)
        self.progress_bar.setFormat("Finished")
        self.progress_bar.setValue(100)
        time.sleep(0.4)
        self.progress_bar.hide()

    def refresh(self):
        try:
            self.refresh_btn.setEnabled(False)  # Disable the button while refreshing
            self.progress_bar.show()
            self.progress_bar.setFormat("Retrieving the pulse list from the server")
            self.progress_bar.setValue(40)
            time.sleep(0.4)

            data_source = self.get_current_source()
            document = data_source.get_pulses_df()

            self.progress_bar.setFormat("Loading pulses into the model")
            self.progress_bar.setValue(80)
            time.sleep(0.4)
            model = self.table.get_current_model()
            model.load_document(document)
            self.update_page_size()
            self.update_page_label()

            self.refresh_btn.setEnabled(True)
            self.progress_bar.setFormat("Finished")
            self.progress_bar.setValue(100)
            time.sleep(0.4)  # Progress bar completed
            self.progress_bar.hide()

        except Exception as e:
            logger.error(f"Error while trying to refresh the model {e}")
            self.refresh_btn.setEnabled(True)
            self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
            self.progress_bar.setFormat(type(e).__name__ + " " + str(e))
            self.progress_bar.setValue(100)
            time.sleep(3)
            self.progress_bar.setStyleSheet("")
            self.progress_bar.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            self.add_pulse()

    def info_pulse(self, index):
        if self.get_current_source().source_type == DS_IMASPY_TYPE:
            row = index.row()
            logger.info("Getting pulse info")
            self.table.get_pulse_info(row)
