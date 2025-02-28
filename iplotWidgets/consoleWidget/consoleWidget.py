import logging

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QStyle, QPushButton, QComboBox, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QCoreApplication


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
                                            QGuiApplication.primaryScreen().availableGeometry(), ), )
        self._pid = QCoreApplication.instance().applicationPid()
        self.setWindowTitle(f"MINT Console ({self._pid})")
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setStyleSheet("""
            QPlainTextEdit
                    {
                        background-color: #2b2b2b;          /* Dark background */
                        color: #FFFFFF;                     /* Light color for the text */
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
        self.severity_label = QLabel("Severity Level:")
        # Layout
        mid_v_layout = QVBoxLayout()
        mid_v_layout.addWidget(self.content)
        bot_h_layout = QHBoxLayout()
        bot_h_layout.addWidget(self.clear_button)
        bot_h_layout.addWidget(self.severity_label, alignment=Qt.AlignmentFlag.AlignRight)
        bot_h_layout.addWidget(self.severity_level)
        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(mid_v_layout)
        main_v_layout.addLayout(bot_h_layout)
        self.setLayout(main_v_layout)

    def setup_logging(self):
        # Log format without milliseconds
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        self.log_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
        console_logger = logging.getLogger()
        console_logger.setLevel("DEBUG")
        console_logger.addHandler(self.log_handler)

    def log_emit(self, record):
        # For each severity level we define a color
        level_colors = {
            'DEBUG': '#A0A0A0',     # Gray for less important logs
            'INFO': '#00CC00',      # Green for general information
            'WARNING': '#FFA500',   # Orange for warnings
            'ERROR': '#FF0000',     # Red for errors
            'CRITICAL': '#8B0000'   # Dark red for critical issues
        }
        msg = self.log_handler.format(record)
        current_level = self.severity_level.currentText()

        if record.levelno >= logging.getLevelName(current_level):
            level_color = level_colors.get(record.levelname, '#FFFFFF')
            level_html = f'<span style="color:{level_color}">{record.levelname}</span>'
            formatted_msg = msg.replace(record.levelname, level_html)
            html_msg = f"<span>{formatted_msg}</span>"
            self.content.appendHtml(html_msg)

    def clear_console(self):
        self.content.clear()

    def show_console(self):
        if not self.isVisible():
            self.show()
        elif self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
