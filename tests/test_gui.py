import importlib.util
import os
import unittest


PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class GuiTests(unittest.TestCase):
    def test_dashboard_history_is_newest_last_and_has_fade_animation(self) -> None:
        from PySide6.QtWidgets import QApplication

        from soundboard.constants import HISTORY_FADE_DURATION_MS
        from soundboard.gui import DashboardPage

        application = QApplication.instance() or QApplication([])
        page = DashboardPage()

        page.addPlayback("first")
        page.addPlayback("second")

        entries = page.getHistoryEntries()
        animations = page.getHistoryAnimations()
        self.assertIn("first", entries[0].text())
        self.assertIn("second", entries[1].text())
        self.assertEqual(HISTORY_FADE_DURATION_MS, animations[0].duration())
        application.processEvents()

    def test_capture_dialog_starts_in_listening_state(self) -> None:
        from PySide6.QtWidgets import QApplication

        from soundboard.gui import ShortcutCaptureDialog

        application = QApplication.instance() or QApplication([])
        dialog = ShortcutCaptureDialog()

        self.assertEqual("Listening…", dialog.getKeysLabel().text())
        self.assertIsNone(dialog.getShortcut())
        application.processEvents()


if __name__ == "__main__":
    unittest.main()

