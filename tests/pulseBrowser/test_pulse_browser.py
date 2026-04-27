# Description: Behavioural tests for PulseBrowser (singleton + page state).

import pytest

from iplotWidgets.pulseBrowser.pulseBrowser import PulseBrowser


@pytest.fixture(autouse=True)
def _reset_pulse_browser_singleton():
    """PulseBrowser caches a single instance via ``__new__``. Reset it
    between tests so each test starts with a fresh widget rather than
    inheriting state from the previous test."""
    PulseBrowser._instance = None
    yield
    PulseBrowser._instance = None


class PulseBrowserSingletonTest:
    def test_two_constructions_return_the_same_instance(self, qapp, app_data_access):
        first = PulseBrowser()
        second = PulseBrowser()
        assert first is second


class PulseBrowserSearchTest:
    def test_empty_search_text_does_not_call_data_source(self, qapp, app_data_access,
                                                          mock_data_source):
        """An empty searchbar must short-circuit before hitting the data
        source — otherwise the user's empty pattern gets translated to
        ``*:*/*`` and pulls the entire pulse list every time."""
        called = {'count': 0}

        def fake_search(text):
            called['count'] += 1
            return mock_data_source.get_pulses_df()

        mock_data_source.search_pulses_df = fake_search
        browser = PulseBrowser()
        browser.searchbar.setText("")

        browser.search()

        assert called['count'] == 0


class PulseBrowserPaginationTest:
    def test_update_page_size_propagates_to_current_model(self, qapp, app_data_access):
        browser = PulseBrowser()
        browser.rows_page.setCurrentText("50")
        browser.update_page_size()
        assert browser.table.get_current_model().page_size == 50

    def test_get_page_size_reads_combo(self, qapp, app_data_access):
        browser = PulseBrowser()
        browser.rows_page.setCurrentText("100")
        assert browser.get_page_size() == 100


@pytest.fixture
def fast_pulse_browser(qapp, app_data_access, monkeypatch):
    """Singleton-reset + ``time.sleep`` no-op + a fresh browser. Same
    pattern as the variable browser's ``fast_browser``."""
    PulseBrowser._instance = None
    import iplotWidgets.pulseBrowser.pulseBrowser as pb_module
    monkeypatch.setattr(pb_module.time, 'sleep', lambda *a, **k: None)
    browser = PulseBrowser()
    yield browser
    PulseBrowser._instance = None


class PulseBrowserRefreshTest:
    """Refresh re-pulls the pulse list from the data source. The
    progress bar must come back enabled and the model must reflect
    the new dataframe; on error the button is re-enabled so the user
    can retry without restarting MINT."""

    def test_refresh_loads_data_source_dataframe_into_model(self, fast_pulse_browser,
                                                             mock_data_source):
        import pandas as pd
        df = pd.DataFrame({
            'Pulse': ['p1', 'p2'],
            'Time From': pd.to_datetime(['2026-04-01', '2026-04-02']),
        })
        mock_data_source.get_pulses_df = lambda **kw: df
        fast_pulse_browser.refresh()
        assert fast_pulse_browser.table.get_current_model().rowCount() > 0

    def test_refresh_swallows_exception_and_re_enables_button(self, fast_pulse_browser,
                                                                mock_data_source):
        def boom(**kw):
            raise RuntimeError('connection refused')
        mock_data_source.get_pulses_df = boom
        fast_pulse_browser.refresh()
        assert fast_pulse_browser.refresh_btn.isEnabled()


class PulseBrowserSearchExtendedTest:
    """``search`` runs the pattern through the data source and feeds
    results into the dedicated ``SEARCH`` model. The progress bar must
    not stay stuck on error and the search button must come back."""

    def test_search_with_pattern_populates_search_model(self, fast_pulse_browser,
                                                          mock_data_source):
        import pandas as pd
        df = pd.DataFrame({
            'Pulse': ['ITER:foo/1'],
            'Time From': pd.to_datetime(['2026-04-01']),
            'Time To': pd.to_datetime(['2026-04-02']),
            'Duration': [pd.Timedelta(days=1)],
            'Status': ['completed'],
            'Description': ['x'],
        })
        mock_data_source.search_pulses_df = lambda text: df
        fast_pulse_browser.searchbar.setText('ITER:foo')
        fast_pulse_browser.search()
        assert fast_pulse_browser.table.models['SEARCH'].rowCount() > 0


class PulseBrowserPaginationButtonsTest:
    def test_previous_pulses_at_first_page_is_safe(self, fast_pulse_browser):
        # No exception even though there's no model data loaded.
        fast_pulse_browser.previous_pulses()

    def test_next_pulses_at_last_page_is_safe(self, fast_pulse_browser):
        fast_pulse_browser.next_pulses()


# pytest-style classes (not unittest.TestCase) need explicit collection
# helpers; expose the classes at module level so pytest discovers them.
TestPulseBrowserSingleton = PulseBrowserSingletonTest
TestPulseBrowserSearch = PulseBrowserSearchTest
TestPulseBrowserPagination = PulseBrowserPaginationTest
TestPulseBrowserRefresh = PulseBrowserRefreshTest
TestPulseBrowserSearchExtended = PulseBrowserSearchExtendedTest
TestPulseBrowserPaginationButtons = PulseBrowserPaginationButtonsTest
