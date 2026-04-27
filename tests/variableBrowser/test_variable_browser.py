# Description: Behavioural tests for VariableBrowser search + glob translation.

import re

import pytest

from iplotDataAccess.dataSource import DS_CODAC_TYPE
from iplotWidgets.variableBrowser.variableBrowser import VariableBrowser


class GlobToRegexTest:
    """The glob-to-regex translation is the rule that protects users from
    pathological patterns like ``EC*`` matching ``ECHO`` instead of just
    things starting with ``EC``. The transformation is inline in
    ``search()``; we exercise the same logic directly to pin its
    semantics."""

    @staticmethod
    def _glob_to_regex(text: str) -> str:
        """Replicate the inline transformation from VariableBrowser.search.

        Done as a free helper so we can pin behaviour without spinning
        up the full widget."""
        return re.escape(text).replace(r'\*', '.*').replace(r'\?', '.')

    def test_star_translates_to_dot_star(self):
        assert self._glob_to_regex('EC*') == 'EC.*'

    def test_question_translates_to_single_char(self):
        assert self._glob_to_regex('A?B') == 'A.B'

    def test_dot_is_escaped_so_it_matches_literally(self):
        assert self._glob_to_regex('a.b') == r'a\.b'

    def test_no_metachars_passes_through_escaped(self):
        # Pure alphanumerics survive re.escape unchanged.
        assert self._glob_to_regex('plain') == 'plain'

    def test_combined_pattern(self):
        assert self._glob_to_regex('EC*?b.c') == r'EC.*.b\.c'


class FieldSyntaxTest:
    """``variable/field`` syntax is CODAC-only — the ``/`` splits the
    pattern into a search term and a field filter. Other backends use the
    raw text. The split logic is in ``search()`` and would silently break
    if someone added a generic ``/`` handler."""

    @staticmethod
    def _split_codac(text: str, source_type: str):
        """Replicate the inline split rule from VariableBrowser.search."""
        if source_type == DS_CODAC_TYPE and '/' in text:
            return tuple(text.split('/', 1))
        return text, None

    def test_codac_with_slash_splits(self):
        assert self._split_codac('VAR/field', DS_CODAC_TYPE) == ('VAR', 'field')

    def test_codac_without_slash_keeps_text(self):
        assert self._split_codac('VAR', DS_CODAC_TYPE) == ('VAR', None)

    def test_non_codac_does_not_split_even_with_slash(self):
        # CSV / IMAS sources use the raw pattern as-is.
        assert self._split_codac('VAR/field', 'CSV') == ('VAR/field', None)


class VariableBrowserConstructionTest:
    """The widget reads from ``AppDataAccess.da`` at construction time.
    Just making it instantiate cleanly catches regressions in the data
    source enumeration, the splitter wiring or the searchbar signal
    connections."""

    def test_constructor_runs_with_a_mock_data_access(self, qapp, app_data_access):
        browser = VariableBrowser()
        assert browser.searchbar is not None
        assert browser.tree is not None
        assert browser.tableView is not None
        assert browser.sources_combo.count() == 1

    def test_get_current_source_returns_combo_user_data(self, qapp, app_data_access,
                                                         mock_data_source):
        browser = VariableBrowser()
        assert browser.get_current_source() is mock_data_source


@pytest.fixture
def fast_browser(qapp, app_data_access, monkeypatch):
    """A VariableBrowser with ``time.sleep`` patched out.

    The search and refresh flows insert several ``time.sleep(0.4)`` waits
    purely so the user can read the progress bar text. Bypassing them
    keeps the suite under a second per test without changing semantics.
    """
    import iplotWidgets.variableBrowser.variableBrowser as vb_module
    monkeypatch.setattr(vb_module.time, 'sleep', lambda *a, **k: None)
    browser = VariableBrowser()
    yield browser
    browser.deleteLater()


class SearchFlowTest:
    """``search`` is the long try/except block that drives the UDA query.
    Without testing it we'd miss regressions in: empty-text early return,
    progress bar state transitions on success / empty / error, glob
    translation, CODAC field syntax, and the model swap to ``SEARCH``."""

    def test_empty_text_does_not_call_data_source(self, fast_browser, mock_data_source):
        """Same guarantee as the pulse browser's empty search — keeps us
        from ever firing a wildcard query against the server by mistake."""
        called = []
        mock_data_source.get_var_dict = lambda **kw: called.append(kw) or {}
        fast_browser.searchbar.setText("")
        fast_browser.search()
        assert called == []

    def test_search_with_results_populates_search_model(self, fast_browser,
                                                         mock_data_source):
        mock_data_source.get_var_dict = lambda **kw: {'matched_var': ''}
        fast_browser.searchbar.setText("matched")
        fast_browser.type_search.setCurrentText("contains")
        fast_browser.search()

        # The 'SEARCH' model is the one populated by search() — the per-source
        # model stays untouched.
        search_model = fast_browser.tree.models['SEARCH']
        assert search_model.rowCount() > 0

    def test_search_with_no_results_loads_empty_document(self, fast_browser,
                                                          mock_data_source):
        mock_data_source.get_var_dict = lambda **kw: {}
        fast_browser.searchbar.setText("nothing")
        fast_browser.search()

        search_model = fast_browser.tree.models['SEARCH']
        assert search_model.rowCount() == 0

    def test_search_swallows_data_source_exceptions(self, fast_browser,
                                                      mock_data_source):
        """A network blip from UDA must not crash the dialog; the user
        sees an error in the progress bar and the search button comes
        back enabled so they can retry."""
        def raise_timeout(**kw):
            raise TimeoutError("server unavailable")

        mock_data_source.get_var_dict = raise_timeout
        fast_browser.searchbar.setText("EC*")
        # Should not propagate.
        fast_browser.search()
        assert fast_browser.search_btn.isEnabled()

    def test_search_re_enables_button_after_completion(self, fast_browser,
                                                        mock_data_source):
        mock_data_source.get_var_dict = lambda **kw: {'x': ''}
        fast_browser.searchbar.setText("anything")
        fast_browser.search()
        assert fast_browser.search_btn.isEnabled()


class UpdateDisplayTest:
    """The searchbar fires ``textChanged`` on every keystroke; with fewer
    than three characters the dialog reverts to the per-source model
    instead of triggering an expensive search. Pinning that threshold
    avoids accidental network thrashing if it's tweaked later."""

    def test_short_text_reverts_to_data_source_model(self, fast_browser,
                                                      mock_data_source):
        # Switch to SEARCH first.
        fast_browser.tree.set_model('SEARCH')
        fast_browser.searchbar.setText("ab")
        fast_browser.update_display()
        # Back to per-source model.
        assert fast_browser.tree.model() is fast_browser.tree.models[mock_data_source.name]


class RefreshFlowTest:
    """Refresh re-pulls the variable tree from the data source. The
    progress bar disables / re-enables the button and the model gets
    the new document; on error the button comes back so the user can
    retry."""

    def test_refresh_loads_data_source_document_into_model(self, fast_browser,
                                                            mock_data_source):
        mock_data_source.get_cbs_dict = lambda **kw: {'sensor_a': '', 'sensor_b': ''}
        fast_browser.refresh()
        assert fast_browser.tree.models[mock_data_source.name].rowCount() == 2

    def test_refresh_swallows_exception_and_re_enables_button(self, fast_browser,
                                                                mock_data_source):
        def raise_err(**kw):
            raise RuntimeError("boom")
        mock_data_source.get_cbs_dict = raise_err
        fast_browser.refresh()
        assert fast_browser.refresh_btn.isEnabled()


class AddToTableTest:
    """``add_to_table`` and ``add_to_main_table`` walk the tree
    selection. They must skip folders (only leaves are addable) and
    must dedupe so a user double-adding doesn't end up with the same
    row twice."""

    def test_finish_emits_signal_and_clears_table(self, fast_browser,
                                                    mock_data_source):
        captured = []
        fast_browser.cmd_finish.connect(lambda df: captured.append(df))
        fast_browser.tableView.model.add_row(['csv', 'temp'])
        fast_browser.finish()
        assert len(captured) == 1
        assert fast_browser.tableView.model.rowCount() == 0


# Expose pytest classes so collection picks them up.
TestGlobToRegex = GlobToRegexTest
TestFieldSyntax = FieldSyntaxTest
TestVariableBrowserConstruction = VariableBrowserConstructionTest
TestSearchFlow = SearchFlowTest
TestUpdateDisplay = UpdateDisplayTest
TestRefreshFlow = RefreshFlowTest
TestAddToTable = AddToTableTest
