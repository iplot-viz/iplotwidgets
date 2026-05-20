"""Shared fixtures for the iplotwidgets test suite.

A single QApplication instance is reused across the whole session — Qt
forbids multiple QApplications in the same process and creating one per
test breaks down with PySide6's signal cleanup. The instance runs in
``offscreen`` mode so the suite is headless on CI.

A lightweight ``mock_data_source`` fixture stands in for
``iplotDataAccess.dataSource.DataSource`` everywhere a widget needs a
data source without touching the network or hitting UDA/IMAS. Tests can
override individual attributes (``source_type``, return values from
``get_pulses_df`` / ``get_var_dict``...) per case.
"""

import os
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Reuse a single offscreen QApplication for the whole test session."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["iplotwidgets-tests"])
    yield app


@pytest.fixture
def mock_data_source():
    """A minimal DataSource stand-in.

    Exposes the attributes the widgets read (``name``, ``source_type``)
    and stub methods that return empty containers by default. Tests
    override what they need with ``ds.<attr> = ...`` or
    ``ds.<method> = lambda ...: ...``.
    """
    import pandas as pd
    from iplotDataAccess.dataSource import DS_CSV_TYPE
    pulse_columns = ["Pulse", "Time From", "Time To", "Duration", "Status",
                     "Description"]
    return SimpleNamespace(
        name="csv_test",
        source_type=DS_CSV_TYPE,
        get_pulses_df=lambda **kwargs: pd.DataFrame(columns=pulse_columns),
        search_pulses_df=lambda text: pd.DataFrame(columns=pulse_columns),
        get_var_dict=lambda **kwargs: {},
        get_cbs_dict=lambda **kwargs: {},
        get_var_fields=lambda variable: {},
        get_pulse_info=lambda **kwargs: {},
    )


@pytest.fixture
def app_data_access(mock_data_source, monkeypatch):
    """Monkey-patch ``AppDataAccess.da`` with a mock.

    Widgets such as ``PulseTable``, ``VariableBrowser`` and ``PulseBrowser``
    read from the ``AppDataAccess.da`` singleton at construction time
    (``default_ds``, ``get_connected_data_sources``...). Initialising the
    real singleton needs a config file and network credentials, neither
    available in CI; this fixture stands in with deterministic defaults.
    """
    from iplotDataAccess.appDataAccess import AppDataAccess
    mock_da = SimpleNamespace(
        default_ds=mock_data_source,
        get_default_ds_name=lambda: mock_data_source.name,
        get_connected_data_sources=lambda: [mock_data_source],
        get_connected_data_source_names=lambda: [mock_data_source.name],
        get_data_source=lambda name: mock_data_source,
    )
    monkeypatch.setattr(AppDataAccess, "da", mock_da)
    return mock_da
