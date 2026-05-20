# Description: Unit tests for the VariableModel JSON-backed tree model.

import unittest
from types import SimpleNamespace

from PySide6.QtCore import Qt

from iplotDataAccess.dataSource import (DS_CODAC_TYPE, DS_CSV_TYPE,
                                        DS_IMASPY_TYPE)
from iplotWidgets.variableBrowser.models.mtJsonModel import (ImasVarItem,
                                                             UdaVarItem,
                                                             VariableModel)


def _make_data_source(source_type: str, var_fields: dict = None):
    """Stand-in for ``DataSource`` exposing only what the model reads.

    ``get_var_fields`` is consulted by ``check_folder`` to decide
    whether a leaf is a plain variable, a status-bearing variable, or a
    nested variable. Tests pass per-variable mappings to drive each
    branch.
    """
    fields = var_fields or {}
    return SimpleNamespace(
        source_type=source_type,
        get_var_fields=lambda variable: fields.get(variable, {}),
        get_var_dict=lambda **kwargs: {},
    )


class CsvLoadTest(unittest.TestCase):
    """CSV sources go through the ``UdaVarItem`` loader (same as CODAC)
    and don't need any field-level lookup."""

    def setUp(self):
        self.ds = _make_data_source(DS_CSV_TYPE)
        self.model = VariableModel(data_source=self.ds)

    def test_load_simple_flat_dict(self):
        document = {'temperature': '', 'pressure': ''}
        self.model.load_document(document)
        self.assertEqual(self.model.rowCount(), 2)

    def test_load_nested_dict_creates_folder(self):
        document = {'sensors': {'temp': '', 'pressure': ''}}
        self.model.load_document(document)
        self.assertEqual(self.model.rowCount(), 1)
        # The single child is a folder containing two leaves.
        sensors_idx = self.model.index(0, 0)
        self.assertEqual(self.model.rowCount(sensors_idx), 2)

    def test_clear_resets_tree_to_empty(self):
        self.model.load_document({'a': '', 'b': ''})
        self.assertEqual(self.model.rowCount(), 2)
        self.model.clear()
        self.assertEqual(self.model.rowCount(), 0)


class CodacLoadAndExpandTest(unittest.TestCase):
    """CODAC sources are lazy — leaves are populated on ``expand`` via
    ``data_source.get_var_dict`` per variable. ``check_folder`` then
    asks for ``get_var_fields`` to determine if each leaf is plain,
    status-bearing or nested."""

    def setUp(self):
        # Per-variable field maps:
        #   - "TEMP_VAR" is a plain variable with 'value' info.
        #   - "STATUS_VAR" is a CSV-style status variable (status_id, val,
        #     secs, severity_id, nanosecs).
        self.var_fields = {
            'TEMP_VAR': {'value': {'type': 'float', 'units': 'K',
                                   'description': 'temperature',
                                   'dimensionality': [1]}},
            'STATUS_VAR': {'status_id': {}, 'val':
                           {'type': 'float', 'units': 'V',
                            'description': 'voltage',
                            'dimensionality': [1]},
                           'secs': {}, 'severity_id': {}, 'nanosecs': {}},
        }
        self.ds = _make_data_source(DS_CODAC_TYPE, self.var_fields)
        self.model = VariableModel(data_source=self.ds)

    def test_load_document_populates_root_children(self):
        self.model.load_document({'TEMP_VAR': '', 'STATUS_VAR': ''})
        self.assertEqual(self.model.rowCount(), 2)

    def test_check_folder_assigns_metadata_to_value_variable(self):
        self.model.load_document({'TEMP_VAR': ''})
        leaf = self.model.root_item.children[0]
        # Metadata is filled in from get_var_fields during check_folder.
        self.assertEqual(leaf.data_type, 'float')
        self.assertEqual(leaf.unit, 'K')
        self.assertEqual(leaf.description, 'temperature')

    def test_check_folder_assigns_metadata_to_status_variable(self):
        self.model.load_document({'STATUS_VAR': ''})
        leaf = self.model.root_item.children[0]
        # The val sub-key carries the metadata for status-bearing leaves.
        self.assertEqual(leaf.data_type, 'float')
        self.assertEqual(leaf.unit, 'V')


class FieldFilterTest(unittest.TestCase):
    """The CODAC ``field_filter`` argument prunes variables whose field
    structure is empty / status-only / value-only — they would otherwise
    appear as dead folders. The filter must also persist so subsequent
    ``expand()`` calls keep filtering."""

    def setUp(self):
        # "MATCHING_VAR" is nested; "OTHER_VAR" is a plain value variable.
        self.var_fields = {
            'MATCHING_VAR': {'configured_field': {'type': 'float',
                                                   'units': '',
                                                   'description': '',
                                                   'dimensionality': [1]},
                             'irrelevant_field': {'type': 'int',
                                                  'units': '',
                                                  'description': '',
                                                  'dimensionality': [1]}},
            'OTHER_VAR': {'value': {'type': 'float', 'units': '',
                                    'description': '', 'dimensionality': [1]}},
        }
        self.ds = _make_data_source(DS_CODAC_TYPE, self.var_fields)
        self.model = VariableModel(data_source=self.ds)

    def test_filter_persists_on_the_model(self):
        self.model.load_document({'MATCHING_VAR': ''},
                                 field_filter='configured')
        self.assertEqual(self.model.field_filter, 'configured')

    def test_filter_prunes_value_only_leaves(self):
        # OTHER_VAR has only a `value` field (no nested subfields), so
        # with a field filter active it must be pruned from the tree.
        self.model.load_document({'OTHER_VAR': ''},
                                 field_filter='configured')
        self.assertEqual(len(self.model.root_item.children), 0)


class ImasLoadTest(unittest.TestCase):
    """IMAS sources go through ``ImasVarItem.load`` which uses
    ``data_type``/``documentation`` keys instead of CODAC's per-variable
    field map."""

    def setUp(self):
        self.ds = _make_data_source(DS_IMASPY_TYPE)
        self.model = VariableModel(data_source=self.ds)

    def test_load_struct_creates_folder(self):
        document = {
            'core_profiles': {
                'data_type': 'structure',
                'documentation': 'core profile data',
                'profiles_1d': {
                    'data_type': 'struct_array',
                    'documentation': '1D profiles',
                }
            }
        }
        self.model.load_document(document)
        self.assertEqual(self.model.rowCount(), 1)
        # core_profiles is a structure → folder; it has 1 child (profiles_1d).
        core_idx = self.model.index(0, 0)
        self.assertEqual(self.model.rowCount(core_idx), 1)

    def test_imas_var_item_is_folder_for_structure_or_struct_array(self):
        item = ImasVarItem(data_type='structure')
        self.assertTrue(item.is_folder())
        item.data_type = 'struct_array'
        self.assertTrue(item.is_folder())
        item.data_type = 'float'
        self.assertFalse(item.is_folder())


class FlagsAndDragDropTest(unittest.TestCase):
    """Folders are not selectable / draggable; leaves are. This is what
    makes drag-drop only work on actual variables, not on the folders
    that hold them."""

    def setUp(self):
        ds = _make_data_source(DS_CSV_TYPE)
        self.model = VariableModel(data_source=ds)
        self.model.load_document({'sensors': {'temp': ''}, 'standalone': ''})

    def test_folder_flag_excludes_drag(self):
        # 'sensors' is a folder.
        folder_idx = self.model.index(0, 0)
        flags = self.model.flags(folder_idx)
        self.assertFalse(bool(flags & Qt.ItemFlag.ItemIsDragEnabled))

    def test_leaf_flag_includes_drag_and_drop(self):
        # 'standalone' is a leaf at the root (alphabetical order: sensors, standalone).
        leaf_idx = self.model.index(1, 0)
        flags = self.model.flags(leaf_idx)
        self.assertTrue(bool(flags & Qt.ItemFlag.ItemIsDragEnabled))

    def test_mime_types_advertises_xml(self):
        self.assertEqual(self.model.mimeTypes(), ['text/xml'])


class UdaVarItemFormattingTest(unittest.TestCase):
    """Display strings shown in the tree must reflect dimension and unit
    in a stable format — these are what the user reads to pick variables."""

    def test_tree_string_with_dimension(self):
        item = UdaVarItem(key='TEMP', unit='K', data_type='float',
                          dimension=[10, 20])
        self.assertEqual(item.get_tree_variable_str(),
                         'TEMP (K) float[10][20]')

    def test_tree_string_without_dimension(self):
        item = UdaVarItem(key='TEMP', unit='K', data_type='float',
                          dimension=[1])
        self.assertEqual(item.get_tree_variable_str(), 'TEMP (K) float')

    def test_table_string_uses_zero_for_each_dimension(self):
        item = UdaVarItem(key='TEMP', dimension=[10, 20])
        self.assertEqual(item.get_table_variable_str(), 'TEMP[0][0]')

    def test_folder_string_returns_key(self):
        item = UdaVarItem(key='SENSORS')
        self.assertEqual(item.get_folder_str(), 'SENSORS')


class UdaVarItemExtractPartsTest(unittest.TestCase):
    """``extract_parts`` is the natural-sort key used to order numeric
    suffixes correctly (``var1, var2, var10`` instead of
    ``var1, var10, var2``). The behaviour must stay stable for the tree
    to keep the ordering users expect."""

    def test_pure_digits_returned_as_int(self):
        self.assertEqual(UdaVarItem.extract_parts('123'), [123])

    def test_pure_letters_returned_as_string(self):
        self.assertEqual(UdaVarItem.extract_parts('abc'), ['abc'])

    def test_alphanumeric_split(self):
        self.assertEqual(UdaVarItem.extract_parts('var10'), ['var', 10])

    def test_natural_sort_orders_numerics(self):
        keys = ['var10', 'var1', 'var2']
        self.assertEqual(sorted(keys, key=UdaVarItem.extract_parts),
                         ['var1', 'var2', 'var10'])


class UdaVarItemGroupCommonPartsTest(unittest.TestCase):
    """``group_common_parts`` collapses ``a/b/c`` flat keys into a nested
    dict shaped like a folder tree. The CODAC nested-variable loader
    relies on this to build a hierarchy from what UDA returns flat."""

    def test_single_segment_keys_passed_through(self):
        result = UdaVarItem.group_common_parts({'a': 1, 'b': 2})
        self.assertEqual(result, {'a': 1, 'b': 2})

    def test_two_segment_keys_grouped_under_common_root(self):
        result = UdaVarItem.group_common_parts({'a/x': 1, 'a/y': 2})
        self.assertEqual(result, {'a': {'x': 1, 'y': 2}})

    def test_deeply_nested_keys(self):
        result = UdaVarItem.group_common_parts({'a/b/c': 1, 'a/b/d': 2})
        self.assertEqual(result, {'a': {'b': {'c': 1, 'd': 2}}})


class CodacNestedVariableTest(unittest.TestCase):
    """``check_folder`` builds nested-variable subtrees when ``get_var_fields``
    returns a multi-key dict that's not the status-id shape and not a
    plain ``{'value': ...}``. This is the common case for CODAC variables
    that expose multiple sub-fields."""

    def test_nested_variable_creates_children_per_field(self):
        var_fields = {
            'NESTED_VAR': {
                'field_a': {'type': 'float', 'units': 'V',
                            'description': 'a', 'dimensionality': [1]},
                'field_b': {'type': 'int', 'units': 'A',
                            'description': 'b', 'dimensionality': [1]},
            },
        }
        ds = _make_data_source(DS_CODAC_TYPE, var_fields)
        model = VariableModel(data_source=ds)
        model.load_document({'NESTED_VAR': ''})

        leaf = model.root_item.children[0]
        self.assertEqual(leaf.data_type, 'nested_variable')
        # Each field becomes an appended child plus the grouped subtree.
        # We assert the flat appended children carry the field metadata.
        appended = [c for c in leaf.children
                    if c.key.startswith('NESTED_VAR/')]
        self.assertEqual(len(appended), 2)
        keys = sorted(c.key for c in appended)
        self.assertEqual(keys, ['NESTED_VAR/field_a', 'NESTED_VAR/field_b'])


class CodacEmptyFieldsTest(unittest.TestCase):
    """An empty ``get_var_fields`` response with a field filter active
    must prune the leaf (silently leaving the user with a clean tree
    rather than dead empty branches)."""

    def test_empty_fields_with_filter_prunes_leaf(self):
        ds = _make_data_source(DS_CODAC_TYPE, {})  # all variables empty
        model = VariableModel(data_source=ds)
        model.load_document({'EMPTY_VAR': ''}, field_filter='anything')
        self.assertEqual(len(model.root_item.children), 0)

    def test_empty_fields_without_filter_keeps_leaf(self):
        ds = _make_data_source(DS_CODAC_TYPE, {})
        model = VariableModel(data_source=ds)
        model.load_document({'EMPTY_VAR': ''})
        self.assertEqual(len(model.root_item.children), 1)


class HasChildAndChildCountTest(unittest.TestCase):
    """The ``flags`` and ``rowCount`` overrides depend on these item
    helpers. A regression here breaks the whole tree rendering."""

    def test_leaf_reports_no_children(self):
        item = UdaVarItem(key='leaf')
        self.assertFalse(item.has_child())
        self.assertEqual(item.child_count(), 0)

    def test_folder_reports_children_count(self):
        parent = UdaVarItem(key='parent')
        for i in range(3):
            parent.append_child(UdaVarItem(key=f'child{i}', parent=parent))
        self.assertTrue(parent.has_child())
        self.assertEqual(parent.child_count(), 3)


if __name__ == '__main__':
    unittest.main()
