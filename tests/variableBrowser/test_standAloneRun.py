# Description: Code to test MTVarSelector as a component

import sys
from PySide6.QtWidgets import QApplication
from iplotWidgets.variableBrowser.variableBrowser import VariableBrowser
from iplotDataAccess.appDataAccess import AppDataAccess
import iplotLogging. setupLogger as Sl

logger = Sl.get_logger(__name__)


class TestVariableBrowser:

    def test_run_app(self):
        app = QApplication(sys. argv)

        logger.info("Running version {} ".format(
            app.applicationVersion()))

        if not AppDataAccess.initialize():
            logger.warning("no data sources found, skipping")
            return

        self.window = VariableBrowser()
        self.window. show()

        self.window.cmd_finish.connect(lambda x: print(self.window.tableView.get_variables_df()))

        assert self.window is not None
        assert hasattr(self.window, 'tableView')

if __name__ == '__main__':
    ob = TestVariableBrowser()
    ob.test_run_app()