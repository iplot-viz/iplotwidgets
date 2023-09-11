from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, QProgressBar
from PySide6.QtCore import Qt, Signal, QCoreApplication
from iplotDataAccess.appDataAccess import AppDataAccess
from iplotWidgets.variableBrowser.variableTree import VariableTree
from iplotWidgets.variableBrowser.variableTable import VariableTable
from iplotWidgets.variableBrowser.tools.converters import parse


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
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.hide()

        self.data_sources = AppDataAccess.da.get_connected_data_sources()
        self.sources_combo = QComboBox()
        self.sources_combo.addItems(self.data_sources)
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

    def get_current_source(self):
        return self.sources_combo.currentText()

    def change_model(self):
        new_source = self.get_current_source()
        self.tree.load_model(new_source)

    def update_display(self):
        text = self.searchbar.text()
        if len(text) < 3:
            self.tree.set_model(self.get_current_source())

    def search(self):
        self.search_btn.setEnabled(False)  # Disable the button while searching
        self.progress_bar.show()
        self.progress_bar.setValue(0)

        text = self.searchbar.text()
        if text == '':
            return
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

        # Progress and GUI updated
        for i, item in enumerate(found):
            progress = int((i/len(found)) * 100)
            self.progress_bar.setValue(progress)
            QCoreApplication.instance().processEvents()

        if found:
            new_dict = parse(found)
            self.tree.models['SEARCH'].load(new_dict)
        else:
            self.tree.models['SEARCH'].load({})

        self.tree.check_folder(self.tree.model()._root_item, data_source_name)

        # Search done
        self.search_btn.setEnabled(True)  # Enable the button after refreshing
        self.progress_bar.setValue(100)  # Progress bar completed
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
        self.refresh_btn.setEnabled(False)  # Disable the button while refreshing
        self.progress_bar.show()

        data_source_name = self.get_current_source()
        lines = AppDataAccess.da.get_cbs_list(data_source_name=data_source_name)

        # Progress and GUI updated
        for i, item in enumerate(lines):
            progress = int((i / len(lines)) * 100)
            self.progress_bar.setValue(progress)
            QCoreApplication.instance().processEvents()

        if lines:
            refresh_dict = parse(lines)
            self.tree.models[data_source_name].load(refresh_dict)
        else:
            refresh_dict_fail = parse({'Error when trying to refresh data source'})
            self.tree.models[data_source_name].load(refresh_dict_fail)

        self.tree.check_folder(self.tree.models[data_source_name]._root_item, data_source_name)

        # Refresh done
        self.refresh_btn.setEnabled(True)  # Enable the button after refreshing
        self.progress_bar.setValue(100)  # Progress bar completed
        self.progress_bar.hide()
