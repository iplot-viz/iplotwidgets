import logging

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QPushButton, QComboBox, QPlainTextEdit, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal


class ConsoleWidget(QWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_handler = logging.Handler()
        self.log_handler.emit = self.log_emit

        self.resize(1000, 550)
        self.setAcceptDrops(True)
        self.setGeometry(QStyle.alignedRect(Qt.LayoutDirection.LeftToRight,
                                            Qt.AlignmentFlag.AlignCenter,
                                            self.size(),
                                            QGuiApplication.primaryScreen().availableGeometry(),
                                            ),
                         )
        self.setWindowTitle("MINT Console")
        # Attributes
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setStyleSheet("""
            QPlainTextEdit
                    {
                        background-color: #2b2b2b;          /* Dark background */
                        color: #ffffff;                     /* Light color for the text */
                        font-family: Consolas, monospace;   /* Monospaced font */
                        font-size: 12px;                    /* Font size */
                        padding: 8px;                       /* Spacing around text */
                    }
        """)
        self.clear_button = QPushButton("Clear console")
        self.clear_button.clicked.connect(self.clear_console)
        self.severity_level = QComboBox()
        self.severity_level.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.severity_level.setCurrentText('WARNING')
        # Layout
        mid_v_layout = QVBoxLayout()
        mid_v_layout.addWidget(self.content)
        bot_h_layout = QHBoxLayout()
        bot_h_layout.addWidget(self.clear_button)
        bot_h_layout.addWidget(self.severity_level)
        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(mid_v_layout)
        main_v_layout.addLayout(bot_h_layout)
        self.setLayout(main_v_layout)

    def setup_logging(self):
        self.log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger = logging.getLogger()
        logger.addHandler(self.log_handler)
        # logger.setLevel(logging.DEBUG)

    def log_emit(self, record):
        msg = self.log_handler.format(record)
        current_level = self.severity_level.currentText()
        if record.levelno >= logging.getLevelName(current_level):
            self.content.appendPlainText(msg)

    def clear_console(self):
        self.content.clear()

    def show_console(self):
        self.show()
