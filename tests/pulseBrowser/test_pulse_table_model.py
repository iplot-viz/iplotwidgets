# Description: Unit tests for PulseTableModel

import unittest
from types import SimpleNamespace

import pandas as pd
from PySide6.QtCore import Qt

from iplotWidgets.pulseBrowser.models.PulseTableModel import PulseTableModel, SELECTED_COL


def _make_model() -> PulseTableModel:
    """A model wired against a non-IMAS data source so the IMAS cache
    branch (which writes to disk) doesn't kick in."""
    return PulseTableModel(data_source=SimpleNamespace(source_type='csv'))


def _df_with_dates() -> pd.DataFrame:
    return pd.DataFrame({
        'Pulse': ['oldest', 'newest', 'middle'],
        'Time From': pd.to_datetime(['2026-01-01', '2026-03-15', '2026-02-10']),
    })


class LoadDocumentDefaultSortTest(unittest.TestCase):
    def setUp(self):
        self.model = _make_model()

    def test_datetime_column_is_sorted_descending(self):
        self.model.load_document(_df_with_dates())
        self.assertEqual(list(self.model.dataframe['Pulse']),
                         ['newest', 'middle', 'oldest'])

    def test_string_date_column_is_not_used_for_sorting(self):
        df = pd.DataFrame({
            'pulse': ['a', 'b', 'c'],
            'date': ['2026-01-01', '2026-03-15', '2026-02-10'],
        })
        self.model.load_document(df)
        self.assertEqual(list(self.model.dataframe['pulse']), ['a', 'b', 'c'])

    def test_no_datetime_column_preserves_order(self):
        df = pd.DataFrame({
            'pulse': ['a', 'b', 'c'],
            'value': [1, 2, 3],
        })
        self.model.load_document(df)
        self.assertEqual(list(self.model.dataframe['pulse']), ['a', 'b', 'c'])


class PaginationTest(unittest.TestCase):
    """Pagination is what lets the browser stay responsive on large pulse
    lists. ``rowCount`` returns at most ``page_size`` and the table view
    only renders the slice for the current page."""

    def setUp(self):
        self.model = _make_model()
        self.df = pd.DataFrame({'Pulse': [f'P{i}' for i in range(50)]})
        self.model.load_document(self.df)
        self.model.page_size = 20

    def test_initial_page_size_default_is_twenty(self):
        fresh = _make_model()
        self.assertEqual(fresh.page_size, 20)

    def test_total_pages_rounds_up_for_partial_last_page(self):
        # 50 rows / 20 per page = 3 pages (20 + 20 + 10).
        self.assertEqual(self.model.get_total_pages(), 3)

    def test_row_count_returns_page_size_on_full_page(self):
        self.assertEqual(self.model.rowCount(), 20)

    def test_row_count_returns_remainder_on_last_page(self):
        self.model.next_page()
        self.model.next_page()
        # Page 2 (zero-indexed) → rows 40..49 → 10 rows.
        self.assertEqual(self.model.rowCount(), 10)

    def test_changing_page_size_resets_to_first_page(self):
        self.model.next_page()
        self.assertGreater(self.model._current_page, 0)
        self.model.page_size = 50
        self.assertEqual(self.model._current_page, 0)

    def test_next_page_at_last_page_is_a_noop(self):
        # 50 rows / 20 per page → pages 0, 1, 2. Walk to the last page.
        self.model.next_page()
        self.model.next_page()
        self.assertEqual(self.model._current_page, 2)
        # Calling next_page() again must not advance past the last page,
        # otherwise rowCount() returns a negative number.
        self.model.next_page()
        self.assertEqual(self.model._current_page, 2)
        self.assertGreaterEqual(self.model.rowCount(), 0)

    def test_get_real_page_is_one_indexed(self):
        self.assertEqual(self.model.get_real_page(), 1)
        self.model.next_page()
        self.assertEqual(self.model.get_real_page(), 2)

    def test_previous_page_at_first_page_is_noop(self):
        self.assertEqual(self.model._current_page, 0)
        self.model.previous_page()
        self.assertEqual(self.model._current_page, 0)

    def test_empty_model_reports_zero_pages_and_real_page(self):
        empty = _make_model()
        self.assertEqual(empty.get_total_pages(), 0)
        self.assertEqual(empty.get_real_page(), 0)

    def test_go_to_page_is_one_indexed(self):
        self.model.go_to_page(3)
        self.assertEqual(self.model.get_real_page(), 3)
        self.assertEqual(self.model.rowCount(), 10)

    def test_go_to_page_ignores_targets_out_of_range(self):
        self.model.go_to_page(2)
        for target in (0, 4, -1):
            self.model.go_to_page(target)
            self.assertEqual(self.model.get_real_page(), 2)


class PageLinksTest(unittest.TestCase):
    """The links shown between the arrows: first and last page plus two
    on each side of the current one, ``None`` where pages are skipped."""

    def test_window_in_the_middle_of_a_long_list(self):
        self.assertEqual(PulseTableModel.page_links(5, 100), [1, None, 3, 4, 5, 6, 7, None, 100])

    def test_window_touching_the_first_page_has_no_gap(self):
        self.assertEqual(PulseTableModel.page_links(1, 100), [1, 2, 3, None, 100])
        self.assertEqual(PulseTableModel.page_links(3, 100), [1, 2, 3, 4, 5, None, 100])

    def test_window_touching_the_last_page_has_no_gap(self):
        self.assertEqual(PulseTableModel.page_links(100, 100), [1, None, 98, 99, 100])

    def test_adjacent_pages_are_not_replaced_by_a_gap(self):
        self.assertEqual(PulseTableModel.page_links(4, 100), [1, 2, 3, 4, 5, 6, None, 100])

    def test_short_lists_link_every_page(self):
        self.assertEqual(PulseTableModel.page_links(2, 3), [1, 2, 3])
        self.assertEqual(PulseTableModel.page_links(1, 1), [1])

    def test_no_pages_no_links(self):
        self.assertEqual(PulseTableModel.page_links(0, 0), [])


class DataFormattingTest(unittest.TestCase):
    """The ``data`` override wraps pandas types in human-readable strings:
    ``pd.Timestamp`` → ``YYYY-MM-DD HH:MM:SS``, ``pd.Timedelta`` → a
    ``HH:MM:SS.usns`` duration. A regression silently breaks every cell
    in the pulse list, so each branch is pinned."""

    def setUp(self):
        self.model = _make_model()
        self.model.load_document(pd.DataFrame({
            'Pulse': ['A', 'B'],
            'Time From': pd.to_datetime(['2026-04-01 10:30:45',
                                          '2026-04-02 11:31:46']),
            'Duration': [pd.Timedelta(seconds=5),
                         pd.Timedelta(days=1, seconds=3661)],
        }))

    def test_timestamp_is_rendered_as_iso_like_string(self):
        # Default sort by Time From DESC → row 0 is the 2026-04-02 timestamp.
        idx = self.model.index(0, self.model.dataframe.columns.get_loc('Time From'))
        rendered = self.model.data(idx, role=Qt.ItemDataRole.DisplayRole)
        self.assertEqual(rendered, '2026-04-02 11:31:46')

    def test_timedelta_under_a_day_omits_day_count(self):
        idx = self.model.index(1, self.model.dataframe.columns.get_loc('Duration'))
        rendered = self.model.data(idx, role=Qt.ItemDataRole.DisplayRole)
        self.assertTrue(rendered.startswith('00:00:05'),
                        f'unexpected duration formatting: {rendered}')

    def test_timedelta_over_a_day_includes_day_count(self):
        idx = self.model.index(0, self.model.dataframe.columns.get_loc('Duration'))
        rendered = self.model.data(idx, role=Qt.ItemDataRole.DisplayRole)
        self.assertIn('1 days', rendered)


class FormatDurationStaticTest(unittest.TestCase):
    """``format_duration`` covers years/days/HMS branches. All inputs are
    deterministic so the output strings can be pinned exactly."""

    def test_seconds_only(self):
        out = PulseTableModel.format_duration(pd.Timedelta(seconds=5))
        self.assertTrue(out.startswith('00:00:05'))

    def test_days_branch(self):
        out = PulseTableModel.format_duration(pd.Timedelta(days=3, hours=2))
        self.assertTrue(out.startswith('3 days '))

    def test_years_branch(self):
        out = PulseTableModel.format_duration(pd.Timedelta(days=400))
        self.assertTrue(out.startswith('1 year'))


class GetPulseTest(unittest.TestCase):
    """``get_pulse`` returns the pulse identifier for a given row.
    For non-IMAS sources it's column 0; for IMAS it concatenates pulse/run."""

    def test_returns_first_column_for_non_imas_source(self):
        model = _make_model()
        model.load_document(pd.DataFrame({'Pulse': ['ITER:foo/1', 'ITER:foo/2']}))
        # After default sort the dataframe order is preserved here (no
        # datetime column), so row 0 is "ITER:foo/1".
        self.assertEqual(model.get_pulse(0), 'ITER:foo/1')


class SelectedColumnTest(unittest.TestCase):
    """The model prepends a ``Selected`` column flagging the pulses the
    caller already uses (MINT's pulse field). It must survive reloads,
    follow later selection changes, sort the selected pulses together with
    the rest most recent first, and leave ``get_pulse`` untouched."""

    def setUp(self):
        self.model = _make_model()
        self.df = pd.DataFrame({
            'Pulse': ['P/1', 'P/2', 'P/3', 'P/4'],
            'Time From': pd.to_datetime(['2026-01-01', '2026-01-02',
                                          '2026-01-03', '2026-01-04']),
        })

    def _column(self, name):
        col = self.model.dataframe.columns.get_loc(name)
        return [self.model.data(self.model.index(r, col), role=Qt.ItemDataRole.DisplayRole)
                for r in range(self.model.rowCount())]

    def test_selected_column_comes_first_and_is_empty_by_default(self):
        self.model.load_document(self.df)
        self.assertEqual(self.model.dataframe.columns[0], SELECTED_COL)
        self.assertEqual(self.model.headerData(0, Qt.Orientation.Horizontal,
                                               Qt.ItemDataRole.DisplayRole), SELECTED_COL)
        self.assertEqual(self._column(SELECTED_COL), ['', '', '', ''])

    def test_selection_set_before_load_is_applied_on_load(self):
        self.model.set_selected_pulses(['P/2'])
        self.model.load_document(self.df)
        # Default order is most recent first: P/4, P/3, P/2, P/1.
        self.assertEqual(self._column(SELECTED_COL), ['', '', '✓', ''])

    def test_selection_change_after_load_refreshes_the_column(self):
        self.model.load_document(self.df)
        self.model.set_selected_pulses([' P/1 ', 'P/4'])
        self.assertEqual(self._column(SELECTED_COL), ['✓', '', '', '✓'])
        self.model.set_selected_pulses([])
        self.assertEqual(self._column(SELECTED_COL), ['', '', '', ''])

    def test_selected_rows_are_highlighted(self):
        self.model.load_document(self.df)
        self.model.set_selected_pulses(['P/4'])
        pulse_col = self.model.dataframe.columns.get_loc('Pulse')
        self.assertIsNotNone(self.model.data(self.model.index(0, pulse_col),
                                             role=Qt.ItemDataRole.BackgroundRole))
        self.assertIsNone(self.model.data(self.model.index(1, pulse_col),
                                          role=Qt.ItemDataRole.BackgroundRole))

    def test_get_pulse_still_returns_the_pulse_identifier(self):
        self.model.set_selected_pulses(['P/3'])
        self.model.load_document(self.df)
        self.assertEqual(self.model.get_pulse(0), 'P/4')

    def test_sorting_by_selected_groups_them_and_keeps_the_rest_most_recent_first(self):
        self.model.load_document(self.df)
        self.model.set_selected_pulses(['P/1', 'P/3'])
        self.model.sort(0, Qt.SortOrder.DescendingOrder)
        self.assertEqual(list(self.model.dataframe['Pulse']), ['P/3', 'P/1', 'P/4', 'P/2'])
        self.model.sort(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(list(self.model.dataframe['Pulse']), ['P/4', 'P/2', 'P/3', 'P/1'])

    def test_empty_source_document_gets_no_selected_column(self):
        self.model.load_document(pd.DataFrame())
        self.assertEqual(self.model.columnCount(), 0)


class LoadNonImasPathTest(unittest.TestCase):
    """The non-IMAS branch of ``load`` simply delegates to the data
    source and feeds the result through ``load_document``."""

    def test_load_calls_data_source_and_populates_model(self):
        df = pd.DataFrame({'Pulse': ['p1', 'p2']})
        ds = SimpleNamespace(
            source_type='csv',
            get_pulses_df=lambda: df,
        )
        model = PulseTableModel(data_source=ds)
        model.load()
        self.assertEqual(model.rowCount(), 2)


class ImasLoadTest(unittest.TestCase):
    """The IMAS branch delegates pulse retrieval to the data source.
    Disk caching, if enabled, belongs to the data-source layer; the model
    only keeps an in-memory ``_loaded`` flag to prevent repeated work
    within the same instance.
    """

    def setUp(self):
        from iplotDataAccess.dataSource import DS_IMASPY_TYPE

        self.df = pd.DataFrame({'pulse': ['1', '2'], 'run': ['1', '2']})
        self.fetch_count = 0

        def fake_fetch():
            self.fetch_count += 1
            return self.df

        self.ds = SimpleNamespace(
            source_type=DS_IMASPY_TYPE,
            get_pulses_df=fake_fetch,
        )

    def test_load_fetches_from_data_source_and_populates_model(self):
        model = PulseTableModel(data_source=self.ds)
        model.load()

        self.assertEqual(self.fetch_count, 1, "first load must hit data source")
        self.assertEqual(model.rowCount(), 2)
        self.assertIs(model.document, self.df)

    def test_loaded_flag_prevents_second_fetch_in_same_instance(self):
        model = PulseTableModel(data_source=self.ds)
        model.load()
        model.load()  # second call must be a no-op.
        self.assertEqual(self.fetch_count, 1)


if __name__ == '__main__':
    unittest.main()
