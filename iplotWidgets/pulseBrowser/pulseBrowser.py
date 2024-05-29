import re
import time

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, \
    QProgressBar
from PySide6.QtCore import Qt, Signal

from iplotDataAccess.dataAccess import DataSource
from iplotDataAccess.dataSourceConfig import DS_CODAC_TYPE
from iplotWidgets.pulseBrowser.pulseTree import PulseTree
from iplotWidgets.variableBrowser.tools.converters import parse_pulses_to_dict
from iplotLogging import setupLogger as setupLog
from iplotDataAccess.appDataAccess import AppDataAccess

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

            self.resize(1000, 800)
            self.width = 840
            self.height = 680
            self.setAcceptDrops(True)
            self.setGeometry(
                QStyle.alignedRect(
                    Qt.LeftToRight,
                    Qt.AlignCenter,
                    self.size(),
                    QGuiApplication.primaryScreen().availableGeometry(),
                ),
            )
            self.flag = ""
            self.tree = PulseTree()
            self.searchbar = QLineEdit()
            self.searchbar.textChanged.connect(self.update_display)

            self.path_input = QLineEdit()
            self.add_to_mint_btn = QPushButton('Add to MINT')
            self.add_to_mint_btn.clicked.connect(self.add_pulse)

            self.search_btn = QPushButton('Search')
            self.search_btn.clicked.connect(self.search)
            self.refresh_btn = QPushButton('Refresh')
            self.refresh_btn.clicked.connect(self.refresh)

            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setParent(self)
            self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.hide()

            self.data_sources = AppDataAccess.da.get_connected_data_sources2()
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

            mid_v_layout = QVBoxLayout()
            mid_v_layout.addWidget(self.tree)
            main_v_layout = QVBoxLayout()
            main_v_layout.addLayout(top_v_layout)
            self.add_layout = main_v_layout.addLayout(mid_v_layout)
            main_v_layout.addLayout(bot_v_layout)
            self.setLayout(main_v_layout)

    def get_current_source(self) -> DataSource:
        return self.sources_combo.currentData()

    def change_model(self):
        new_source = self.get_current_source()
        self.tree.load_model(new_source)

    def update_display(self):
        text = self.searchbar.text()
        if len(text) < 3:
            self.tree.set_model(self.get_current_source().name)

    def add_pulse(self):
        indexes = self.tree.selectedIndexes()
        pulses = []
        indexes = [ix.internalPointer() for ix in indexes]
        for ix in indexes:
            value = ix.key
            pulses.append(value)

        # Check implemented
        if self.flag == "table":
            self.cmd_finish.emit(pulses)
        elif self.flag == "button":
            self.srch_finish.emit(pulses)
        self.tree.clearSelection()

    def search(self):
        text = self.searchbar.text()
        if text == '':
            return
        self.search_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setFormat("Retrieving the variable list from the server")
        self.progress_bar.setValue(40)
        time.sleep(0.4)

        self.tree.set_model('SEARCH')

        pattern = 'ITER:*/*'

        # Check if it is a number
        if re.match(r'^\d+$', text):
            pattern = f'ITER:*/{text}'
        else:
            parts = text.split('/')
            folder = parts[0] if parts[0] != '*' else ''
            number = parts[1] if len(parts) > 1 else ''

            if folder and number:
                pattern = f'ITER:{folder}*/{number}'
            elif folder and not number:
                pattern = f'ITER:{folder}*/*'
            elif not folder and number:
                pattern = f'ITER:*/{number}'

        data_source = self.get_current_source()
        self.tree.models['SEARCH'].data_source = data_source
        found = AppDataAccess.da.get_pulse_list(data_source_name=data_source.name, pattern=pattern)

        if found:
            self.progress_bar.setFormat("Loading pulses into the model")
            self.progress_bar.setValue(80)
            if data_source.dtype == DS_CODAC_TYPE:
                found = parse_pulses_to_dict(found)
            self.tree.models['SEARCH'].load_document(found)
            time.sleep(0.4)
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
            self.progress_bar.setFormat("Empty model")
            self.progress_bar.setValue(80)
            self.progress_bar.setStyleSheet("")
            time.sleep(2)
            self.tree.models['SEARCH'].load_document({})

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
            document = AppDataAccess.da.get_pulse_list(data_source_name=data_source.name)

            self.progress_bar.setFormat("Loading pulses into the model")
            self.progress_bar.setValue(80)
            time.sleep(0.4)
            if data_source.dtype == DS_CODAC_TYPE:
                document = parse_pulses_to_dict(document)
            self.tree.models[data_source.name].load_document(document)

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
