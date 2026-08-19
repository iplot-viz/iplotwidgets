# Description: Behavioural tests for VariableBrowser search + glob translation.

import pytest

from iplotDataAccess.dataSource import DS_CODAC_TYPE
from iplotWidgets.variableBrowser.variableBrowser import VariableBrowser


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

    def test_search_translates_glob_wildcards_into_regex(self, fast_browser,
                                                          mock_data_source):
        # ``EC*`` must reach the data source as ``.*EC.*.*`` (contains-mode)
        # and not as the raw glob — otherwise UDA receives a regex that
        # matches anything containing 'E'.
        captured = {}
        mock_data_source.get_var_dict = lambda **kw: captured.update(kw) or {}
        fast_browser.type_search.setCurrentText("contains")
        fast_browser.searchbar.setText("EC*")
        fast_browser.search()
        assert captured["pattern"] == ".*EC.*.*"
        assert "field" not in captured

    def test_search_escapes_regex_metacharacters(self, fast_browser,
                                                  mock_data_source):
        # A literal dot in the user input must be escaped so it does not
        # become 'any character' in the regex passed to the data source.
        captured = {}
        mock_data_source.get_var_dict = lambda **kw: captured.update(kw) or {}
        fast_browser.type_search.setCurrentText("startsWith")
        fast_browser.searchbar.setText("a.b")
        fast_browser.search()
        assert captured["pattern"] == r"a\.b.*"

    def test_search_splits_codac_field_syntax(self, fast_browser, mock_data_source):
        # ``VAR/field`` on a CODAC source must split into pattern + field
        # kwarg; on non-CODAC sources the slash is passed through verbatim.
        mock_data_source.source_type = DS_CODAC_TYPE
        captured = {}
        mock_data_source.get_var_dict = lambda **kw: captured.update(kw) or {}
        fast_browser.type_search.setCurrentText("contains")
        fast_browser.searchbar.setText("VAR/field")
        fast_browser.search()
        assert captured["pattern"] == ".*VAR.*"
        assert captured["field"] == "field"

    def test_search_non_codac_does_not_split_on_slash(self, fast_browser,
                                                       mock_data_source):
        captured = {}
        mock_data_source.get_var_dict = lambda **kw: captured.update(kw) or {}
        fast_browser.type_search.setCurrentText("contains")
        fast_browser.searchbar.setText("VAR/field")
        fast_browser.search()
        assert captured["pattern"] == ".*VAR/field.*"
        assert "field" not in captured


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


HMI_VARS = {
    'VAR-A:FT01': {'description': 'Coolant flow', 'units': 'm3/s', 'type': 'float'},
    'VAR-B:TT01': {'description': 'Magnet temperature', 'units': 'K', 'type': 'float'},
}


@pytest.fixture
def hmi_browser(qapp, app_data_access, mock_data_source, monkeypatch):
    """A VariableBrowser whose data source has a controls metadata server."""
    import iplotWidgets.variableBrowser.variableBrowser as vb_module
    monkeypatch.setattr(vb_module.time, 'sleep', lambda *a, **k: None)
    mock_data_source.controls_metadata = 'http://meta-host:3000'
    mock_data_source.get_hmi_var_dict = lambda refresh=False: dict(HMI_VARS)
    browser = VariableBrowser()
    yield browser
    browser.deleteLater()


class HmiVariablesTest:
    """The 'Important variables' check box drives the controls metadata
    (HMI) mode: it only appears for sources with a controlsmetadata
    server, replaces the tree with the REST-provided variable list, and
    switches the search to a local one that also matches description
    and unit. None of it may fire per-variable server lookups."""

    def test_checkbox_hidden_without_metadata_server(self, fast_browser):
        assert fast_browser.hmi_check.isHidden()

    def test_checkbox_shown_with_metadata_server(self, hmi_browser):
        assert not hmi_browser.hmi_check.isHidden()

    def test_toggle_loads_hmi_model_with_metadata(self, hmi_browser, mock_data_source):
        lookups = []
        mock_data_source.get_var_fields = lambda variable: lookups.append(variable)
        hmi_browser.hmi_check.setChecked(True)

        model = hmi_browser.tree.model()
        assert model is hmi_browser.tree.models[f'{mock_data_source.name}:HMI']
        leaves = {item.key: item for item in model.root_item.children}
        assert set(leaves) == set(HMI_VARS)
        assert leaves['VAR-A:FT01'].unit == 'm3/s'
        assert leaves['VAR-A:FT01'].description == 'Coolant flow'
        assert leaves['VAR-A:FT01'].data_type == 'float'
        assert lookups == []

    def test_hmi_search_matches_description(self, hmi_browser, mock_data_source):
        queries = []
        mock_data_source.get_var_dict = lambda **kw: queries.append(kw) or {}
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.searchbar.setText('temperature')
        hmi_browser.type_search.setCurrentText('contains')
        hmi_browser.search()

        search_model = hmi_browser.tree.models['SEARCH']
        assert [item.key for item in search_model.root_item.children] == ['VAR-B:TT01']
        assert queries == []

    def test_hmi_search_matches_unit(self, hmi_browser):
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.searchbar.setText('m3')
        hmi_browser.type_search.setCurrentText('contains')
        hmi_browser.search()

        search_model = hmi_browser.tree.models['SEARCH']
        assert [item.key for item in search_model.root_item.children] == ['VAR-A:FT01']

    def test_hmi_search_still_matches_the_name(self, hmi_browser):
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.searchbar.setText('VAR-A*')
        hmi_browser.type_search.setCurrentText('contains')
        hmi_browser.search()

        search_model = hmi_browser.tree.models['SEARCH']
        assert [item.key for item in search_model.root_item.children] == ['VAR-A:FT01']

    def test_uncheck_returns_to_source_model(self, hmi_browser, mock_data_source):
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.hmi_check.setChecked(False)
        assert hmi_browser.tree.model() is hmi_browser.tree.models[mock_data_source.name]

    def test_refresh_in_hmi_mode_refetches_the_list(self, hmi_browser, mock_data_source):
        calls = []

        def get_hmi_var_dict(refresh=False):
            calls.append(refresh)
            return dict(HMI_VARS)

        mock_data_source.get_hmi_var_dict = get_hmi_var_dict
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.refresh()
        assert calls == [False, True]

    def test_short_text_reverts_to_hmi_model(self, hmi_browser, mock_data_source):
        hmi_browser.hmi_check.setChecked(True)
        hmi_browser.tree.set_model('SEARCH')
        hmi_browser.searchbar.setText('ab')
        hmi_browser.update_display()
        assert hmi_browser.tree.model() is hmi_browser.tree.models[f'{mock_data_source.name}:HMI']


# Expose pytest classes so collection picks them up.
TestVariableBrowserConstruction = VariableBrowserConstructionTest
TestSearchFlow = SearchFlowTest
TestUpdateDisplay = UpdateDisplayTest
TestRefreshFlow = RefreshFlowTest
TestAddToTable = AddToTableTest
TestHmiVariables = HmiVariablesTest
