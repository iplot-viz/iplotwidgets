# Description: The page of what a loaded module offers, from its docstrings (mint#207).

import importlib
import sys
import textwrap

import numpy as np
import pytest
from PySide6.QtCore import QUrl

from iplotWidgets.moduleImporter.moduleDescription import (ModuleDescription, functions_of, modules_of,
                                                         signature_and_summary)


@pytest.fixture
def package(tmp_path, monkeypatch):
    """A package as MCTF's: no function in its __init__, which imports the submodule that has them."""
    root = tmp_path / 'mctflike'
    root.mkdir()
    (root / '__init__.py').write_text('"""Tools of the test facility."""\nfrom . import coils\n')
    (root / 'coils.py').write_text(textwrap.dedent('''\
        """Quantities of the coils.

        Every function takes arrays."""
        from numpy import array


        def current_density(current, area=1.0):
            """The current density of a coil, in A/m2.

            Parameters
            ----------
            current : array, in A
            """
            return array(current) / area


        def _helper():
            return None
        '''))
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module('mctflike')
    yield module
    for name in [name for name in sys.modules if name.split('.')[0] == 'mctflike']:
        del sys.modules[name]


class ModuleContentsTest:
    def test_a_package_reaches_the_functions_of_its_submodules(self, package):
        modules = modules_of(package, walk=True)
        assert [module.__name__ for module in modules] == ['mctflike', 'mctflike.coils']
        # Its own functions only: not the ones it imports, nor the private ones.
        assert [name for name, _ in functions_of(modules[1])] == ['current_density']

    def test_a_module_imported_from_another_is_described_alone(self, package):
        assert modules_of(package, walk=False) == [package]

    def test_a_function_says_how_it_is_called_and_what_it_does(self, package):
        assert signature_and_summary(package.coils.current_density) == ('(current, area=1.0)',
                                                                        'The current density of a coil, in A/m2.')

    def test_a_function_written_in_c_says_it_in_its_docstring(self):
        signature, summary = signature_and_summary(np.abs)
        assert signature.startswith('(x, /')
        assert summary == 'Calculate the absolute value element-wise.'


class ModuleDescriptionTest:
    def test_the_page_lists_the_functions_and_a_click_opens_one(self, qapp, package):
        page = ModuleDescription()
        page.describe('import mctflike as m', package)
        index = page.toPlainText()
        assert 'Tools of the test facility.' in index
        assert 'current_density(current, area=1.0)' in index
        assert 'The current density of a coil, in A/m2.' in index

        page.anchorClicked.emit(QUrl('function:mctflike.coils:current_density'))
        assert 'current : array, in A' in page.toPlainText()
        page.anchorClicked.emit(QUrl('back'))
        assert page.toPlainText() == index

    def test_without_a_module_it_says_what_to_do(self, qapp):
        page = ModuleDescription()
        assert page.toPlainText() == 'Select a module to read what it offers.'
        page.describe('import gone', None)
        assert page.toPlainText() == 'import gone is not loaded.'


TestModuleContents = ModuleContentsTest
TestModuleDescription = ModuleDescriptionTest
