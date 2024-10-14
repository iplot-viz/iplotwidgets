from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, Signal
from iplotWidgets.moduleImporter.moduleTable import ModuleTable
from iplotProcessing.tools.parsers import Parser
from typing import List

from iplotLogging import setupLogger as setupLog

logger = setupLog.get_logger(__name__)


class ModuleImporter(QWidget):
    cmd_finish = Signal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.resize(500, 400)
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
        self.setWindowTitle("Load new modules")
        self.parser = Parser()

        if not self.parser.has_access_to_config():
            show_msg("Error: You do not have the necessary permissions to modify the configuration file. "
                     "Change the environment variable: IPLOT_PMODULE_PATH value")

        self.tableView = ModuleTable()
        self.searchbar = QLineEdit()

        self.path_input = QLineEdit()
        self.clear_module = QPushButton('Clear selected module')
        self.clear_module.clicked.connect(self.clear_selected_module)
        self.clear_all_module = QPushButton('Clear all modules')
        self.clear_all_module.clicked.connect(self.reset_modules)

        self.search_btn = QPushButton('Add')
        self.search_btn.clicked.connect(self.check_module)

        top_h_layout = QHBoxLayout()
        top_h_layout.addWidget(self.searchbar)
        top_h_layout.addWidget(self.search_btn)
        top_v_layout = QVBoxLayout()
        top_v_layout.addLayout(top_h_layout)

        bot_h_layout = QHBoxLayout()
        bot_h_layout.addWidget(self.clear_module)
        bot_h_layout.addWidget(self.clear_all_module)

        mid_h_layout = QHBoxLayout()
        mid_h_layout.addWidget(self.tableView)
        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(top_v_layout)
        main_v_layout.addLayout(mid_h_layout)
        main_v_layout.addLayout(bot_h_layout)
        self.setLayout(main_v_layout)

        # Show available modules when loading the window.
        self.starter_modules()

    def starter_modules(self):
        modules = self.get_current_modules()
        self.tableView.model.total_default_modules = self.parser.get_total_default_modules()
        for module in modules:
            self.tableView.model.add_row([module])

    def get_current_modules(self) -> List[str]:
        return self.parser.get_modules()

    def check_module(self):
        text = self.searchbar.text()

        try:
            self.parser.load_modules(text)
            self.parser.add_module_to_config(text)
        except Exception as e:
            logger.exception(e)
            show_msg(f"Error {str(e)}: cannot import module")
            return

        # If the module was loaded correctly, it will be shown in the module table.
        modules = self.parser.get_modules()
        data_list = self.tableView.get_variables_list()
        for value in modules:
            if value not in data_list:
                self.tableView.model.add_row([value])

    def clear_selected_module(self):
        index = self.tableView.selectedIndexes()
        rows = [ix.row() for ix in index]
        valid_rows = self.parser.clear_modules(rows)
        self.tableView.remove_selected_module(valid_rows)

    def reset_modules(self):
        self.parser.reset_modules()
        self.tableView.clear_table(self.parser.get_total_default_modules())

    def finish(self):
        df = self.tableView.get_variables_df()
        self.cmd_finish.emit(df)
        self.tableView.clear_table(self.parser.get_total_default_modules())


def show_msg(message):
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("Error")
    box.setText(message)
    box.exec_()
