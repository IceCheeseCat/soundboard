from __future__ import annotations

from collections.abc import Iterable

from soundboard.constants import MAX_SHORTCUT_KEYS


MODIFIER_KEYS = ("ctrl", "shift", "alt", "meta")
MODIFIER_ALIASES = {
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "shift_l": "shift",
    "shift_r": "shift",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt_gr": "alt",
    "cmd": "meta",
    "cmd_l": "meta",
    "cmd_r": "meta",
}


def normalizeKeyName(p_keyName: str) -> str:
    key_name = p_keyName.strip().lower().replace("key.", "")
    key_name = MODIFIER_ALIASES.get(key_name, key_name)
    if len(key_name) == 1:
        return key_name

    return key_name.replace(" ", "_")


def canonicalizeShortcut(p_keys: Iterable[str]) -> tuple[str, ...]:
    normalized_keys = {normalizeKeyName(key) for key in p_keys if key.strip()}
    if not normalized_keys:
        raise ValueError("Press at least one key.")
    if len(normalized_keys) > MAX_SHORTCUT_KEYS:
        raise ValueError(f"Shortcuts may contain at most {MAX_SHORTCUT_KEYS} keys.")
    if normalized_keys.issubset(MODIFIER_KEYS):
        raise ValueError("A shortcut must contain at least one non-modifier key.")

    modifiers = [key for key in MODIFIER_KEYS if key in normalized_keys]
    ordinary_keys = sorted(normalized_keys.difference(MODIFIER_KEYS))
    return tuple(modifiers + ordinary_keys)


def shortcutToStorageKey(p_shortcut: Iterable[str]) -> str:
    return "+".join(canonicalizeShortcut(p_shortcut))


def shortcutFromStorageKey(p_storageKey: str) -> tuple[str, ...]:
    return canonicalizeShortcut(p_storageKey.split("+"))


def formatShortcut(p_shortcut: Iterable[str]) -> str:
    labels = {
        "ctrl": "Ctrl",
        "shift": "Shift",
        "alt": "Alt",
        "meta": "Meta",
        "space": "Space",
    }
    return "+".join(labels.get(key, key.upper()) for key in canonicalizeShortcut(p_shortcut))


class ShortcutCaptureState:
    def __init__(self) -> None:
        self.m_pressedKeys: set[str] = set()
        self.m_isComplete = False

    def getPressedKeys(self) -> set[str]:
        return set(self.m_pressedKeys)

    def setPressedKeys(self, p_pressedKeys: set[str]) -> None:
        self.m_pressedKeys = set(p_pressedKeys)

    def getIsComplete(self) -> bool:
        return self.m_isComplete

    def setIsComplete(self, p_isComplete: bool) -> None:
        self.m_isComplete = p_isComplete

    def press(self, p_keyName: str) -> None:
        if self.m_isComplete:
            return

        key_name = normalizeKeyName(p_keyName)
        candidate_keys = self.m_pressedKeys | {key_name}
        if len(candidate_keys) > MAX_SHORTCUT_KEYS:
            raise ValueError(f"Shortcuts may contain at most {MAX_SHORTCUT_KEYS} keys.")

        self.m_pressedKeys = candidate_keys

    def release(self, p_keyName: str) -> tuple[str, ...]:
        if self.m_isComplete:
            raise ValueError("Shortcut capture is already complete.")

        key_name = normalizeKeyName(p_keyName)
        if key_name not in self.m_pressedKeys:
            raise ValueError("Released key was not part of the captured shortcut.")

        shortcut = canonicalizeShortcut(self.m_pressedKeys)
        self.m_isComplete = True
        return shortcut
