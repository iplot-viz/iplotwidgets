# Description: Behavioural tests for VariableTree.

import pytest

from iplotWidgets.variableBrowser.variableTree import VariableTree


@pytest.fixture
def tree(qapp, app_data_access):
    """Build a VariableTree wired to the mock data access singleton.
    Each test gets a fresh widget."""
    widget = VariableTree()
    yield widget
    widget.deleteLater()


class TreeConstructionTest:
    def test_models_dict_starts_with_search_and_default_data_source(self, tree, mock_data_source):
        assert 'SEARCH' in tree.models
        assert mock_data_source.name in tree.models

    def test_get_model_returns_currently_set_model(self, tree, mock_data_source):
        tree.set_model(mock_data_source.name)
        assert tree.get_model() is tree.models[mock_data_source.name]


class SetModelTest:
    def test_unknown_data_source_name_is_ignored(self, tree):
        previous = tree.model()
        tree.set_model('does-not-exist')
        # Calling set_model with an unknown key is a silent no-op so a
        # typo doesn't blow away the user's current view.
        assert tree.model() is previous


class HandleItemEnteredTest:
    """The tooltip handler skips folder rows (they have no metadata to
    show) and renders a 4-line tooltip for leaves. Pre-existing PySide
    versions used to crash on invalid indexes — the early return here
    is a defensive guard worth pinning."""

    def test_invalid_index_is_silently_ignored(self, tree):
        from PySide6.QtCore import QModelIndex
        # Should not raise.
        tree.handle_item_entered(QModelIndex())

    def test_folder_index_is_silently_skipped(self, tree, mock_data_source):
        """No assertion fires; we just confirm the call doesn't raise
        when the hovered item happens to be a folder."""
        # Load a folder structure into the default model.
        tree.models[mock_data_source.name].load_document({
            'folder_a': {'leaf_x': '', 'leaf_y': ''}
        })
        tree.set_model(mock_data_source.name)
        folder_idx = tree.model().index(0, 0)
        # Should not raise (the early-return guard kicks in).
        tree.handle_item_entered(folder_idx)


# Expose pytest classes.
TestTreeConstruction = TreeConstructionTest
TestSetModel = SetModelTest
TestHandleItemEntered = HandleItemEnteredTest
