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
    browser.deleteLater()
    qapp.processEvents()
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


class PulseBrowserTimeWindowTest:
    """*Started between* keeps the pulses that started in a time window, with
    or without a pattern. Its times are those of the pulses, in UTC, as the
    table shows them; the pulses of some data sources have none."""

    @staticmethod
    def _pulses(*starts):
        import pandas as pd
        started = pd.to_datetime(list(starts))
        return pd.DataFrame({
            'Pulse': [f'ITER:foo/{k}' for k in range(len(starts))],
            'Time From': started,
            'Time To': started + pd.Timedelta(minutes=5),
            'Duration': [pd.Timedelta(minutes=5)] * len(starts),
            'Status': ['completed'] * len(starts),
            'Description': [''] * len(starts),
        })

    @staticmethod
    def _window(browser, start, end):
        from PySide6.QtCore import QDateTime, Qt
        browser.started_between.setChecked(True)
        browser.started_from.setDateTime(QDateTime.fromString(start, Qt.DateFormat.ISODate))
        browser.started_to.setDateTime(QDateTime.fromString(end, Qt.DateFormat.ISODate))

    @staticmethod
    def _found(browser):
        return list(browser.table.models['SEARCH'].dataframe['Pulse'])

    def test_a_search_keeps_the_pulses_that_started_in_the_time_window(self, fast_pulse_browser,
                                                                        mock_data_source):
        mock_data_source.search_pulses_df = lambda text: self._pulses(
            '2026-04-01T09:30', '2026-04-01T10:30', '2026-04-01T11:30', '2026-04-01T12:30')
        fast_pulse_browser.searchbar.setText('ITER:foo')
        self._window(fast_pulse_browser, '2026-04-01T10:00:00', '2026-04-01T12:00:00')

        fast_pulse_browser.search()

        # Latest first, as the table sorts them.
        assert self._found(fast_pulse_browser) == ['ITER:foo/2', 'ITER:foo/1']

    def test_without_a_pattern_the_time_window_looks_through_every_pulse(self, fast_pulse_browser,
                                                                          mock_data_source):
        searched = []
        mock_data_source.search_pulses_df = searched.append
        mock_data_source.get_pulses_df = lambda **kw: self._pulses('2026-04-01T09:30', '2026-04-01T10:30')
        self._window(fast_pulse_browser, '2026-04-01T10:00:00', '2026-04-01T12:00:00')

        fast_pulse_browser.search()

        assert searched == []
        assert self._found(fast_pulse_browser) == ['ITER:foo/1']

    def test_unchecked_the_time_window_leaves_the_search_alone(self, fast_pulse_browser, mock_data_source):
        mock_data_source.search_pulses_df = lambda text: self._pulses('2026-04-01T09:30', '2026-04-01T12:30')
        fast_pulse_browser.searchbar.setText('ITER:foo')
        self._window(fast_pulse_browser, '2026-04-01T10:00:00', '2026-04-01T12:00:00')

        fast_pulse_browser.started_between.setChecked(False)
        fast_pulse_browser.search()

        assert not fast_pulse_browser.started_from.isEnabled()
        assert not fast_pulse_browser.started_to.isEnabled()
        assert self._found(fast_pulse_browser) == ['ITER:foo/1', 'ITER:foo/0']

    def test_return_in_a_time_of_the_window_searches_instead_of_adding_the_pulse_selected(
            self, fast_pulse_browser, mock_data_source):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        mock_data_source.get_pulses_df = lambda **kw: self._pulses('2026-04-01T09:30', '2026-04-01T10:30')
        fast_pulse_browser.refresh()
        fast_pulse_browser.flag = 'time_range'
        added = []
        fast_pulse_browser.srch_finish.connect(added.append)
        self._window(fast_pulse_browser, '2026-04-01T10:00:00', '2026-04-01T12:00:00')
        fast_pulse_browser.table.selectRow(1)
        fast_pulse_browser.show()
        try:
            # Keys go to the field that has the focus, in the window that is active.
            fast_pulse_browser.activateWindow()
            assert QTest.qWaitForWindowActive(fast_pulse_browser)
            fast_pulse_browser.started_to.setFocus()
            QTest.keyClick(fast_pulse_browser.started_to, Qt.Key.Key_Return)
        finally:
            fast_pulse_browser.hide()

        assert added == []
        assert self._found(fast_pulse_browser) == ['ITER:foo/1']

    def test_the_time_window_is_only_for_pulses_that_tell_when_they_started(self, fast_pulse_browser):
        import pandas as pd
        from types import SimpleNamespace
        no_times = pd.DataFrame({'pulseId': ['local:a/1'], 'Status': ['completed']})
        csv = SimpleNamespace(name='no_times', source_type='csv', get_pulses_df=lambda **kw: no_times,
                              search_pulses_df=lambda text: no_times)
        fast_pulse_browser.started_between.setChecked(True)
        assert fast_pulse_browser.started_between.isEnabled()

        fast_pulse_browser.sources_combo.addItem(csv.name, userData=csv)
        fast_pulse_browser.sources_combo.setCurrentText(csv.name)
        fast_pulse_browser.searchbar.setText('local')
        fast_pulse_browser.search()

        assert not fast_pulse_browser.started_between.isEnabled()
        assert not fast_pulse_browser.started_from.isEnabled()
        assert list(fast_pulse_browser.table.models['SEARCH'].dataframe['pulseId']) == ['local:a/1']
        fast_pulse_browser.sources_combo.setCurrentText('csv_test')
        assert fast_pulse_browser.started_between.isEnabled()
        assert fast_pulse_browser.started_from.isEnabled()


class PulseBrowserSelectedPulsesTest:
    """``set_selected_pulses`` is how MINT tells the browser which pulses
    are already in use. The flag must reach the model on screen, the
    search results and any model created afterwards. With
    ``set_selected_pulses_provider`` the browser asks instead: whenever it
    is shown and on ``refresh_selected_pulses``."""

    def _df(self, *pulses):
        import pandas as pd
        return pd.DataFrame({
            'Pulse': list(pulses),
            'Time From': pd.to_datetime(['2026-04-01'] * len(pulses)),
        })

    def test_selection_reaches_the_current_model(self, fast_pulse_browser, mock_data_source):
        mock_data_source.get_pulses_df = lambda **kw: self._df('A/1', 'A/2')
        fast_pulse_browser.refresh()
        fast_pulse_browser.set_selected_pulses(['A/2'])
        model = fast_pulse_browser.table.get_current_model()
        assert list(model.dataframe['Selected']) == [False, True]

    def test_selection_reaches_search_results(self, fast_pulse_browser, mock_data_source):
        fast_pulse_browser.set_selected_pulses(['B/1'])
        mock_data_source.search_pulses_df = lambda text: self._df('B/1', 'B/2')
        fast_pulse_browser.searchbar.setText('B')
        fast_pulse_browser.search()
        model = fast_pulse_browser.table.models['SEARCH']
        assert list(model.dataframe['Selected']) == [True, False]

    def test_selection_reaches_models_created_later(self, fast_pulse_browser):
        from types import SimpleNamespace
        fast_pulse_browser.set_selected_pulses(['C/2'])
        source = SimpleNamespace(name='later', source_type='csv',
                                 get_pulses_df=lambda: self._df('C/1', 'C/2'))
        fast_pulse_browser.table.load_model(source)
        model = fast_pulse_browser.table.models['later']
        assert list(model.dataframe['Selected']) == [False, True]

    def test_provider_is_asked_when_the_browser_is_shown(self, fast_pulse_browser, mock_data_source):
        mock_data_source.get_pulses_df = lambda **kw: self._df('D/1', 'D/2')
        fast_pulse_browser.refresh()
        in_use = ['D/1']
        fast_pulse_browser.set_selected_pulses_provider(lambda: list(in_use))
        model = fast_pulse_browser.table.get_current_model()
        assert list(model.dataframe['Selected']) == [True, False]
        in_use[:] = ['D/2']
        fast_pulse_browser.show()
        try:
            assert list(model.dataframe['Selected']) == [False, True]
        finally:
            fast_pulse_browser.hide()

    def test_refresh_selected_pulses_pulls_from_the_provider(self, fast_pulse_browser, mock_data_source):
        mock_data_source.get_pulses_df = lambda **kw: self._df('E/1', 'E/2')
        fast_pulse_browser.refresh()
        in_use = []
        fast_pulse_browser.set_selected_pulses_provider(lambda: list(in_use))
        model = fast_pulse_browser.table.get_current_model()
        assert list(model.dataframe['Selected']) == [False, False]
        in_use.append('E/2')
        fast_pulse_browser.refresh_selected_pulses()
        assert list(model.dataframe['Selected']) == [False, True]

    def test_without_a_provider_the_explicit_selection_survives_show(self, fast_pulse_browser, mock_data_source):
        mock_data_source.get_pulses_df = lambda **kw: self._df('F/1', 'F/2')
        fast_pulse_browser.refresh()
        fast_pulse_browser.set_selected_pulses(['F/1'])
        fast_pulse_browser.refresh_selected_pulses()
        fast_pulse_browser.show()
        try:
            model = fast_pulse_browser.table.get_current_model()
            assert list(model.dataframe['Selected']) == [True, False]
        finally:
            fast_pulse_browser.hide()


class PulseBrowserPaginationButtonsTest:
    def test_previous_pulses_at_first_page_is_safe(self, fast_pulse_browser):
        # No exception even though there's no model data loaded.
        fast_pulse_browser.previous_pulses()

    def test_next_pulses_at_last_page_is_safe(self, fast_pulse_browser):
        fast_pulse_browser.next_pulses()


def _page_link_texts(browser):
    layout = browser.page_links_layout
    return [layout.itemAt(i).widget().text() for i in range(layout.count())]


def _page_link_button(browser, page):
    layout = browser.page_links_layout
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget.text() == str(page):
            return widget
    raise AssertionError(f"no link to page {page} in {_page_link_texts(browser)}")


class PulseBrowserPageLinksTest:
    """Direct page links sit between the arrows and follow the page
    state, so a long pulse list is reachable without paging one by one."""

    def _load(self, browser, mock_data_source, rows):
        import pandas as pd
        mock_data_source.get_pulses_df = lambda **kw: pd.DataFrame({'Pulse': [f'P{i}' for i in range(rows)]})
        browser.refresh()

    def test_no_links_without_pulses(self, fast_pulse_browser):
        assert _page_link_texts(fast_pulse_browser) == []

    def test_links_show_the_ends_and_the_window_around_the_current_page(self, fast_pulse_browser,
                                                                          mock_data_source):
        self._load(fast_pulse_browser, mock_data_source, rows=2000)
        fast_pulse_browser.go_to_page(5)
        assert _page_link_texts(fast_pulse_browser) == ['1', '…', '3', '4', '5', '6', '7', '…', '100']
        assert fast_pulse_browser.table.get_current_page() == 5

    def test_clicking_a_link_turns_the_page(self, fast_pulse_browser, mock_data_source):
        self._load(fast_pulse_browser, mock_data_source, rows=100)
        _page_link_button(fast_pulse_browser, 3).click()
        assert fast_pulse_browser.table.get_current_page() == 3
        assert fast_pulse_browser.page_label.text() == 'Page 3 of 5'
        assert fast_pulse_browser.table.get_current_model().rowCount() == 20
        _page_link_button(fast_pulse_browser, 5).click()
        assert fast_pulse_browser.table.get_current_page() == 5
        assert not fast_pulse_browser.next_page.isEnabled()

    def test_current_page_link_is_marked_and_inert(self, fast_pulse_browser, mock_data_source):
        self._load(fast_pulse_browser, mock_data_source, rows=100)
        fast_pulse_browser.next_pulses()
        current = _page_link_button(fast_pulse_browser, 2)
        assert current.isChecked() and not current.isEnabled()
        assert _page_link_button(fast_pulse_browser, 3).isEnabled()

    def test_links_follow_the_arrows_and_the_page_size(self, fast_pulse_browser, mock_data_source):
        self._load(fast_pulse_browser, mock_data_source, rows=100)
        fast_pulse_browser.next_pulses()
        assert _page_link_button(fast_pulse_browser, 2).isChecked()
        fast_pulse_browser.rows_page.setCurrentText("50")
        assert _page_link_texts(fast_pulse_browser) == ['1', '2']
        assert _page_link_button(fast_pulse_browser, 1).isChecked()


# pytest-style classes (not unittest.TestCase) need explicit collection
# helpers; expose the classes at module level so pytest discovers them.
TestPulseBrowserSingleton = PulseBrowserSingletonTest
TestPulseBrowserSearch = PulseBrowserSearchTest
TestPulseBrowserPagination = PulseBrowserPaginationTest
TestPulseBrowserRefresh = PulseBrowserRefreshTest
TestPulseBrowserSearchExtended = PulseBrowserSearchExtendedTest
TestPulseBrowserTimeWindow = PulseBrowserTimeWindowTest
TestPulseBrowserSelectedPulses = PulseBrowserSelectedPulsesTest
TestPulseBrowserPaginationButtons = PulseBrowserPaginationButtonsTest
TestPulseBrowserPageLinks = PulseBrowserPageLinksTest
