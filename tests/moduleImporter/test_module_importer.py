# Description: Behavioural tests for ModuleImporter (Parser-mocked).

import re

import pytest

from iplotWidgets.moduleImporter.moduleImporter import ModuleImporter


@pytest.fixture
def fake_parser(monkeypatch):
    """Stand in for ``iplotProcessing.tools.parsers.Parser``.

    ModuleImporter calls a handful of Parser methods (``get_modules``,
    ``add_module_to_config``, ``clear_modules``...) plus reads the
    regex ``pattern`` attribute. The widget must not touch the real
    config file or import real Python modules, so we intercept the
    ``Parser`` symbol before construction and hand it a stub.
    """
    state = {
        'modules': ['default_a', 'default_b'],
        'default_total': 2,
        'config_writes': [],
        'load_calls': [],
        'has_access': True,
    }

    class _StubParser:
        # Mirrors the real Parser regex shape ('module' named group).
        pattern = re.compile(r"(?P<module>[A-Za-z_][\w.]*)")

        def has_access_to_config(self):
            return state['has_access']

        def get_modules(self):
            return list(state['modules'])

        def get_modules_names(self):
            return [self.pattern.match(m).groupdict()['module']
                    for m in state['modules']]

        def get_total_default_modules(self):
            return state['default_total']

        def load_modules(self, text):
            state['load_calls'].append(text)

        def add_module_to_config(self, text):
            state['config_writes'].append(text)
            state['modules'].append(text)

        def reset_modules(self):
            state['modules'] = state['modules'][:state['default_total']]

        def clear_modules(self, rows):
            keep = [m for i, m in enumerate(state['modules']) if i not in rows]
            state['modules'] = keep
            return rows

    import iplotWidgets.moduleImporter.moduleImporter as mi_module
    monkeypatch.setattr(mi_module, 'Parser', _StubParser)
    yield state


@pytest.fixture
def importer(qapp, fake_parser, monkeypatch):
    """A constructed ModuleImporter wired against the stub parser.

    QMessageBox.exec_ is patched out to avoid a modal dialog blocking
    the test runner if the constructor tries to warn about a
    read-only config."""
    import iplotWidgets.moduleImporter.moduleImporter as mi_module
    monkeypatch.setattr(mi_module.QMessageBox, 'exec_', lambda self: 0)
    widget = ModuleImporter()
    yield widget
    widget.deleteLater()


class StarterModulesTest:
    def test_starter_modules_populates_table_from_parser(self, importer, fake_parser):
        # Two default modules should appear in the table after construction.
        assert importer.tableView.model.rowCount() == 2

    def test_total_default_modules_is_set_on_model(self, importer, fake_parser):
        assert importer.tableView.model.total_default_modules == 2


class CheckModuleTest:
    def test_check_module_adds_new_module_to_config_and_table(self, importer,
                                                                fake_parser):
        importer.searchbar.setText("new_module")
        importer.check_module()

        assert "new_module" in fake_parser['config_writes']
        # The new module shows up in the table after the parser loaded it.
        assert importer.tableView.model.rowCount() == 3

    def test_check_module_skips_already_imported(self, importer, fake_parser):
        importer.searchbar.setText("default_a")
        importer.check_module()

        # No write to the config and no new row in the table.
        assert "default_a" not in fake_parser['config_writes']
        assert importer.tableView.model.rowCount() == 2

    def test_check_module_with_loader_exception_does_not_add(self, importer,
                                                                fake_parser,
                                                                monkeypatch):
        def boom(text):
            raise RuntimeError("module not found")
        monkeypatch.setattr(importer.parser, 'load_modules', boom)
        importer.searchbar.setText("broken_module")
        importer.check_module()

        # Failure must not silently add the module to the config.
        assert "broken_module" not in fake_parser['config_writes']


class ResetModulesTest:
    def test_reset_keeps_default_modules_and_clears_table_rest(self, importer,
                                                                  fake_parser):
        # Add a user module first.
        importer.searchbar.setText("user_extra")
        importer.check_module()
        assert importer.tableView.model.rowCount() == 3

        importer.reset_modules()

        assert importer.tableView.model.rowCount() == 2
        assert fake_parser['modules'] == ['default_a', 'default_b']


class FinishTest:
    def test_finish_emits_dataframe_and_clears_to_defaults(self, importer,
                                                              fake_parser):
        captured = []
        importer.cmd_finish.connect(lambda df: captured.append(df))

        importer.searchbar.setText("user_x")
        importer.check_module()
        importer.finish()

        assert len(captured) == 1
        # After finish the table is back to just the default modules.
        assert importer.tableView.model.rowCount() == 2


# Expose pytest classes for collection.
TestStarterModules = StarterModulesTest
TestCheckModule = CheckModuleTest
TestResetModules = ResetModulesTest
TestFinish = FinishTest
