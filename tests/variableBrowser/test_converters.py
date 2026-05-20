# Description: Unit tests for variableBrowser.tools.converters

import unittest

from iplotWidgets.variableBrowser.tools.converters import parse_imaspy_pulses


class ParseImaspyPulsesTest(unittest.TestCase):
    """The function is currently a passthrough but is part of the public
    contract — pinning that contract guards against silent semantic
    changes (e.g. someone replacing it with a parser that drops fields)."""

    def test_passes_input_through_unchanged(self):
        lines = [{'pulse': 1}, {'pulse': 2}]
        self.assertEqual(parse_imaspy_pulses(lines), lines)

    def test_empty_input(self):
        self.assertEqual(parse_imaspy_pulses([]), [])


if __name__ == '__main__':
    unittest.main()
