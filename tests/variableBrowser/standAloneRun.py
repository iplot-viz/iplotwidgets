# Description: Code to test MTVarSelector as a component

import sys
from PySide6.QtWidgets import QApplication
from iplotWidgets.variableBrowser.variableBrowser import VariableBrowser
from iplotDataAccess.appDataAccess import AppDataAccess
import iplotLogging.setupLogger as Sl

logger = Sl.get_logger(__name__)


class TestVariableBrowser:

    def test_run_app(self):
        app = QApplication(sys.argv)

        # Logger
        logger.info("Running version {} ".format(
            app.applicationVersion()))

        if not AppDataAccess.initialize():
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
