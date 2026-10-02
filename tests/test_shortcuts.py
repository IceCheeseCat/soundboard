import unittest

from soundboard.shortcuts import (
    ShortcutCaptureState,
    canonicalizeShortcut,
    formatShortcut,
)


class ShortcutTests(unittest.TestCase):
    def test_normalizes_modifiers_and_orders_keys(self) -> None:
        shortcut = canonicalizeShortcut(["x", "Key.shift_r", "ctrl_l"])

        self.assertEqual(("ctrl", "shift", "x"), shortcut)
        self.assertEqual("Ctrl+Shift+X", formatShortcut(shortcut))

    def test_rejects_more_than_three_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3"):
            canonicalizeShortcut(["ctrl", "shift", "alt", "v"])

    def test_rejects_modifier_only_shortcut(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-modifier"):
            canonicalizeShortcut(["ctrl", "shift"])

    def test_capture_completes_on_first_release(self) -> None:
        capture = ShortcutCaptureState()
        capture.press("ctrl")
        capture.press("shift")
        capture.press("x")

        shortcut = capture.release("x")

        self.assertEqual(("ctrl", "shift", "x"), shortcut)
        self.assertTrue(capture.getIsComplete())

if __name__ == "__main__":
    unittest.main()
