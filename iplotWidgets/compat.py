"""Names from iplotDataAccess that changed, so iplotWidgets runs with new and older releases."""

try:
    from iplotDataAccess.dataSource import DS_IMAS_TYPE
except ImportError:  # iplotDataAccess 1.5.2 and earlier
    from iplotDataAccess.dataSource import DS_IMASPY_TYPE as DS_IMAS_TYPE

try:
    from iplotDataAccess.dataSource import DS_PYUDA_TYPE
except ImportError:  # iplotDataAccess without the pyuda data source
    DS_PYUDA_TYPE = "PYUDA"
