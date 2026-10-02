import importlib.util
import unittest


PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None


class FakeKey:
    def __init__(self, p_name: str, p_character: str | None = None) -> None:
        self.m_name = p_name
        self.m_character = p_character

    def getName(self) -> str:
        return self.m_name

    def setName(self, p_name: str) -> None:
        self.m_name = p_name

    @property
    def char(self) -> str | None:
        return self.m_character

    @char.setter
    def char(self, p_character: str | None) -> None:
        self.m_character = p_character

    def __str__(self) -> str:
        return self.m_name


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class HotkeyTests(unittest.TestCase):
    def test_held_shortcut_triggers_only_once_until_release(self) -> None:
        from soundboard.hotkeys import GlobalHotkeyService

        service = GlobalHotkeyService()
        service.setBindings({("ctrl", "x"): "sound-id"})
        control = FakeKey("Key.ctrl_l")
        key_x = FakeKey("'x'", "x")

        self.assertEqual([], service.processPress(control))
        self.assertEqual(["sound-id"], service.processPress(key_x))
        self.assertEqual([], service.processPress(key_x))

        service.processRelease(key_x)

        self.assertEqual(["sound-id"], service.processPress(key_x))

    def test_suppression_prevents_shortcuts_during_capture(self) -> None:
        from soundboard.hotkeys import GlobalHotkeyService

        service = GlobalHotkeyService()
        service.setBindings({("f8",): "sound-id"})
        service.setIsSuppressed(True)

        self.assertEqual([], service.processPress(FakeKey("Key.f8")))


if __name__ == "__main__":
    unittest.main()

