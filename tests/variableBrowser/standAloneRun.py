# Description: Code to test MTVarSelector as a component
# Author: Jhon Steeven Cabanilla Alvarado

import sys
import os
from PySide6.QtWidgets import QApplication
from iplotwidgets.variableBrowser import VariableBrowser
from iplotlib.interface.iplotSignalAdapter import AccessHelper
from iplotDataAccess.appDataAccess import AppDataAccess
import iplotLogging.setupLogger as ls
from importlib import metadata
from mint.app.dirs import DEFAULT_DATA_SOURCES_CFG

logger = ls.get_logger(__name__)


class TestVariableBrowser:

    def test_run_app(self):
        app = QApplication(sys.argv)

        # Logger
        logger.info("Running version {} ".format(
            app.applicationVersion()))

        if not AppDataAccess.loadConfiguration():
            logger.error("no data sources found, exiting")
            sys.exit(-1)

        # When the app starts, the SearchVar Widget is shown
        self.window = VariableBrowser()
        self.window.show()

        self.window.cmd_finish.connect(lambda x: print(self.window.tableView.get_variables_df()))

        return app.exec()


if __name__ == '__main__':
    ob = TestVariableBrowser()
    sys.exit(ob.test_run_app())

