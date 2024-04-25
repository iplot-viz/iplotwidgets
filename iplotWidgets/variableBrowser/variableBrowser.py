import time

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, \
    QProgressBar
from PySide6.QtCore import Qt, Signal
from iplotWidgets.variableBrowser.variableTree import VariableTree
from iplotWidgets.variableBrowser.variableTable import VariableTable
from iplotWidgets.variableBrowser.tools.converters import parse
from iplotLogging import setupLogger as setupLog
from iplotDataAccess.appDataAccess import AppDataAccess

logger = setupLog.get_logger(__name__)


class VariableBrowser(QWidget):
    cmd_finish = Signal(object)

    def __init__(self, *args, **kwargs):
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
        self.tree = VariableTree()
        self.tableView = VariableTable()
        self.searchbar = QLineEdit()
        self.searchbar.textChanged.connect(self.update_display)

        self.path_input = QLineEdit()
        self.add_to_list_btn = QPushButton('Add to list')
        self.add_to_list_btn.clicked.connect(self.add_to_table)
        self.clear_btn = QPushButton('Clear')
        self.clear_btn.clicked.connect(self.tableView.clear_table)
        self.finish_btn = QPushButton('Add to table')

        self.search_btn = QPushButton('Search')
        self.search_btn.clicked.connect(self.search)
        self.refresh_btn = QPushButton('Refresh')
        self.refresh_btn.clicked.connect(self.refresh)
        self.type_search = QComboBox()
        self.type_search.addItems(['contains', 'startsWith', 'endsWith'])
        # self.type_search.currentTextChanged.connect(self.update_display)

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
        self.sources_combo.currentTextChanged.connect(self.change_model)

        top_h_layout = QHBoxLayout()
        top_h_layout.addWidget(self.sources_combo)
        top_h_layout.addWidget(self.refresh_btn)
        top_h_layout.addWidget(self.searchbar)
        top_h_layout.addWidget(self.type_search)
        top_h_layout.addWidget(self.search_btn)
        top_v_layout = QVBoxLayout()
        top_v_layout.addLayout(top_h_layout)
        top_v_layout.addWidget(self.progress_bar)

        bot_v_layout = QVBoxLayout()
        bot_h_layout = QHBoxLayout()
        bot_h_layout.addWidget(self.add_to_list_btn)
        bot_h_layout.addWidget(self.clear_btn)
        bot_v_layout.addLayout(bot_h_layout)
        bot_v_layout.addWidget(self.finish_btn)

        mid_h_layout = QHBoxLayout()
        mid_h_layout.addWidget(self.tree)
        mid_h_layout.addWidget(self.tableView)
        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(top_v_layout)
        self.add_layout = main_v_layout.addLayout(mid_h_layout)
        main_v_layout.addLayout(bot_v_layout)
        self.setLayout(main_v_layout)

        self.finish_btn.clicked.connect(self.finish)

    def get_current_source(self) -> str:
        return self.sources_combo.currentData()

    def change_model(self):
        new_source = self.get_current_source()
        self.tree.load_model(new_source)

    def update_display(self):
        text = self.searchbar.text()
        if len(text) < 3:
            self.tree.set_model(self.get_current_source())

    def search(self):
        text = self.searchbar.text()
        if text == '':
            return
        self.search_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setFormat("Retrieving the variable list from the server")
        self.progress_bar.setValue(25)
        time.sleep(0.4)

        self.tree.set_model('SEARCH')

        type_search = self.type_search.currentText()

        if type_search == 'startsWith':
            pattern = f'{text}.*'
        elif type_search == 'contains':
            pattern = f'.*{text}.*'
        elif type_search == 'endsWith':
            pattern = f'.*{text}'
        else:
            pattern = ''
        data_source_name = self.get_current_source()
        found = AppDataAccess.da.get_var_list(data_source_name=data_source_name, pattern=pattern)

        if found:
            self.progress_bar.setFormat("Loading variables into the model")
            self.progress_bar.setValue(50)
            new_dict = parse(found)
            self.tree.models['SEARCH'].load(new_dict)
            time.sleep(0.4)
            self.progress_bar.setFormat("Checking the information of the root variables")
            self.progress_bar.setValue(75)
            self.tree.check_folder(self.tree.model().root_item, data_source_name)
            time.sleep(0.4)
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
            self.progress_bar.setFormat("Empty model")
            self.progress_bar.setValue(50)
            self.progress_bar.setStyleSheet("")
            time.sleep(2)
            self.tree.models['SEARCH'].load({})

        # Search done
        self.search_btn.setEnabled(True)
        self.progress_bar.setFormat("Finished")
        self.progress_bar.setValue(100)
        time.sleep(0.4)
        self.progress_bar.hide()

    def add_to_table(self):
        indexes = self.tree.selectedIndexes()
        data_list = self.tableView.get_variables_list()
        indexes = [ix.internalPointer() for ix in indexes]
        for ix in indexes:

            value = ix.key + ix.get_dimension_str_0()
            if not ix.has_child() and [self.get_current_source(), value] not in data_list:
                self.tableView.model.add_row([self.get_current_source(), value])
        self.tree.clearSelection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            self.add_to_table()
        elif event.key() == Qt.Key.Key_Delete:
            self.tableView.remove_from_table()

    def finish(self):
        df = self.tableView.get_variables_df()
        self.cmd_finish.emit(df)
        self.tableView.clear_table()

    def refresh(self):
        try:
            self.refresh_btn.setEnabled(False)  # Disable the button while refreshing
            self.progress_bar.show()
            self.progress_bar.setFormat("Retrieving the variable list from the server")
            self.progress_bar.setValue(25)
            time.sleep(0.4)

            data_source_name = self.get_current_source()
            lines = AppDataAccess.da.get_cbs_list(data_source_name=data_source_name)

            self.progress_bar.setFormat("Loading variables into the model")
            self.progress_bar.setValue(50)
            time.sleep(0.4)
            if lines:
                refresh_dict = parse(lines)
                self.tree.models[data_source_name].load(refresh_dict)
            else:
                self.tree.models[data_source_name].load({})

            self.progress_bar.setFormat("Checking the information of the root variables")
            self.progress_bar.setValue(75)
            time.sleep(0.4)
            self.tree.check_folder(self.tree.models[data_source_name].root_item, data_source_name)

            # Refresh done
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
