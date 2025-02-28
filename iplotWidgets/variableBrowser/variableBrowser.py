import time

import pandas as pd
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, \
    QProgressBar, QSplitter
from PySide6.QtCore import Qt, Signal

from iplotDataAccess.dataSource import DataSource
from iplotWidgets.variableBrowser.variableTree import VariableTree
from iplotWidgets.variableBrowser.variableTable import VariableTable
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
                Qt.LayoutDirection.LeftToRight,
                Qt.AlignmentFlag.AlignCenter,
                self.size(),
                QGuiApplication.primaryScreen().availableGeometry(),
            ),
        )

        self.setWindowTitle("Variable search")
        self.tree = VariableTree()
        self.tableView = VariableTable()
        self.searchbar = QLineEdit()
        self.searchbar.textChanged.connect(self.update_display)
        self.searchbar.returnPressed.connect(self.search)

        self.path_input = QLineEdit()
        self.add_to_list_btn = QPushButton('Add to list')
        self.add_to_list_btn.clicked.connect(self.add_to_table)
        self.clear_btn = QPushButton('Clear')
        self.clear_btn.clicked.connect(self.tableView.clear_table)
        self.finish_btn = QPushButton('Flush && Add to main table')
        self.main_finish_btn = QPushButton('Add to main table')
        self.main_finish_btn.clicked.connect(self.add_to_main_table)

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
        top_h_layout.addWidget(self.type_search)
        top_h_layout.addWidget(self.search_btn)
        top_v_layout = QVBoxLayout()
        top_v_layout.addLayout(top_h_layout)
        top_v_layout.addWidget(self.progress_bar)

        tree_container = QWidget()
        tree_layout = QVBoxLayout()
        tree_layout.addWidget(self.tree)
        tree_buttons_layout = QHBoxLayout()
        tree_buttons_layout.addWidget(self.add_to_list_btn)
        tree_buttons_layout.addWidget(self.main_finish_btn)
        tree_layout.addLayout(tree_buttons_layout)
        tree_container.setLayout(tree_layout)
        tree_container.setMinimumWidth(300)
        table_container = QWidget()
        table_layout = QVBoxLayout()
        table_layout.addWidget(self.tableView)
        table_buttons_layout = QHBoxLayout()
        table_buttons_layout.addWidget(self.finish_btn)
        table_buttons_layout.addWidget(self.clear_btn)
        table_layout.addLayout(table_buttons_layout)
        table_container.setLayout(table_layout)
        table_container.setMinimumWidth(300)

        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(tree_container)
        self.splitter.addWidget(table_container)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(top_v_layout)
        main_v_layout.addWidget(self.splitter)
        self.setLayout(main_v_layout)

        self.finish_btn.clicked.connect(self.finish)

    def get_current_source(self) -> DataSource:
        return self.sources_combo.currentData()

    def change_model(self):
        new_source = self.get_current_source()
        self.tree.load_model(new_source)

    def update_display(self):
        text = self.searchbar.text()
        if len(text) < 3:
            self.tree.set_model(self.get_current_source().name)

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

        type_search = self.type_search.currentText()

        if type_search == 'startsWith':
            pattern = f'{text}.*'
        elif type_search == 'contains':
            pattern = f'.*{text}.*'
        elif type_search == 'endsWith':
            pattern = f'.*{text}'
        else:
            pattern = ''
        data_source = self.get_current_source()
        self.tree.models['SEARCH'].data_source = data_source
        try:
            found = data_source.get_var_dict(pattern=pattern)

            if found:
                self.progress_bar.setFormat("Loading variables into the model")
                self.progress_bar.setValue(80)
                self.tree.models['SEARCH'].load_document(found)
                time.sleep(0.4)
            else:
                self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
                self.progress_bar.setFormat("Empty model")
                self.progress_bar.setValue(80)
                self.progress_bar.setStyleSheet("")
                time.sleep(2)
                self.tree.models['SEARCH'].load_document({})
        except Exception as e:
            logger.error(f"Exception {e} while triying to load new module")
            self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: #FF6666;}")
            self.progress_bar.setFormat(f"Error while loading module")
            self.progress_bar.setValue(90)
            self.progress_bar.setStyleSheet("")
            time.sleep(2)

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
            value = ix.get_table_variable_str()
            if not ix.has_child() and [self.get_current_source().name, value] not in data_list:
                self.tableView.model.add_row([self.get_current_source().name, value])
        self.tree.clearSelection()

    def add_to_main_table(self):
        dataframe = pd.DataFrame(columns=['DS', 'Variable'])
        indexes = self.tree.selectedIndexes()
        indexes = [ix.internalPointer() for ix in indexes]
        for ix in indexes:
            value = ix.get_table_variable_str()
            if not ix.has_child():
                dataframe.loc[len(dataframe)] = [self.get_current_source().name, value]
        self.tree.clearSelection()
        self.cmd_finish.emit(dataframe)

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
            self.progress_bar.setValue(40)
            time.sleep(0.4)

            data_source = self.get_current_source()
            document = data_source.get_cbs_dict()
            self.progress_bar.setFormat("Loading variables into the model")
            self.progress_bar.setValue(80)
            time.sleep(0.4)
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
