from __future__ import annotations

import os
import platform
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from soundboard.shortcuts import normalizeKeyName


def isGlobalHotkeySupported() -> tuple[bool, str]:
    if platform.system() != "Linux":
        return True, ""

    session_type = os.environ.get("XDG_SESSION_TYPE", "").casefold()
    if session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        return (
            False,
            "Global shortcuts are unavailable on Wayland. Log into an X11 session "
            "to use background keybindings.",
        )

    return True, ""


class GlobalHotkeyService(QObject):
    m_soundTriggered = Signal(str)
    m_listenerError = Signal(str)

    def __init__(self, p_listenerFactory: Callable[..., Any] | None = None) -> None:
        super().__init__()
        self.m_listenerFactory = p_listenerFactory
        self.m_listener: Any | None = None
        self.m_bindings: dict[tuple[str, ...], str] = {}
        self.m_pressedKeys: set[str] = set()
        self.m_triggeredShortcuts: set[tuple[str, ...]] = set()
        self.m_isSuppressed = False
        self.m_lock = threading.RLock()

    def getSoundTriggeredSignal(self) -> Signal:
        return self.m_soundTriggered

    def getListenerErrorSignal(self) -> Signal:
        return self.m_listenerError

    def getStatusMessage(self) -> str:
        return "Global shortcuts active"

    def getListenerFactory(self) -> Callable[..., Any] | None:
        return self.m_listenerFactory

    def setListenerFactory(self, p_listenerFactory: Callable[..., Any] | None) -> None:
        self.m_listenerFactory = p_listenerFactory

    def getListener(self) -> Any | None:
        return self.m_listener

    def setListener(self, p_listener: Any | None) -> None:
        self.m_listener = p_listener

    def getBindings(self) -> dict[tuple[str, ...], str]:
        with self.m_lock:
            return dict(self.m_bindings)

    def setBindings(self, p_bindings: dict[tuple[str, ...], str]) -> None:
        with self.m_lock:
            self.m_bindings = dict(p_bindings)
            self.m_triggeredShortcuts.clear()

    def getPressedKeys(self) -> set[str]:
        with self.m_lock:
            return set(self.m_pressedKeys)

    def setPressedKeys(self, p_pressedKeys: set[str]) -> None:
        with self.m_lock:
            self.m_pressedKeys = set(p_pressedKeys)

    def getTriggeredShortcuts(self) -> set[tuple[str, ...]]:
        with self.m_lock:
            return set(self.m_triggeredShortcuts)

    def setTriggeredShortcuts(self, p_shortcuts: set[tuple[str, ...]]) -> None:
        with self.m_lock:
            self.m_triggeredShortcuts = set(p_shortcuts)

    def getIsSuppressed(self) -> bool:
        with self.m_lock:
            return self.m_isSuppressed

    def setIsSuppressed(self, p_isSuppressed: bool) -> None:
        with self.m_lock:
            self.m_isSuppressed = p_isSuppressed
            self.m_pressedKeys.clear()
            self.m_triggeredShortcuts.clear()

    def getLock(self) -> threading.RLock:
        return self.m_lock

    def setLock(self, p_lock: threading.RLock) -> None:
        self.m_lock = p_lock

    def start(self) -> None:
        if self.m_listener is not None:
            return

        supported, reason = isGlobalHotkeySupported()
        if not supported:
            self.m_listenerError.emit(reason)
            return

        try:
            listener_factory = self.m_listenerFactory
            if listener_factory is None:
                from pynput import keyboard

                listener_factory = keyboard.Listener

            self.m_listener = listener_factory(
                on_press=self._handlePress,
                on_release=self._handleRelease,
            )
            self.m_listener.start()
        except Exception as error:
            self.m_listener = None
            self.m_listenerError.emit(f"Unable to start global shortcuts: {error}")

    def stop(self) -> None:
        listener = self.m_listener
        self.m_listener = None
        if listener is not None:
            listener.stop()

        with self.m_lock:
            self.m_pressedKeys.clear()
            self.m_triggeredShortcuts.clear()

    def processPress(self, p_key: Any) -> list[str]:
        key_name = self._keyToName(p_key)
        sound_ids: list[str] = []
        with self.m_lock:
            if self.m_isSuppressed or key_name is None:
                return sound_ids

            self.m_pressedKeys.add(key_name)
            for shortcut, sound_id in self.m_bindings.items():
                if shortcut in self.m_triggeredShortcuts:
                    continue
                if set(shortcut).issubset(self.m_pressedKeys):
                    self.m_triggeredShortcuts.add(shortcut)
                    sound_ids.append(sound_id)

        return sound_ids

    def processRelease(self, p_key: Any) -> None:
        key_name = self._keyToName(p_key)
        if key_name is None:
            return

        with self.m_lock:
            self.m_pressedKeys.discard(key_name)
            self.m_triggeredShortcuts = {
                shortcut
                for shortcut in self.m_triggeredShortcuts
                if key_name not in shortcut
            }

    def _handlePress(self, p_key: Any) -> None:
        for sound_id in self.processPress(p_key):
            self.m_soundTriggered.emit(sound_id)

    def _handleRelease(self, p_key: Any) -> None:
        self.processRelease(p_key)

    def _keyToName(self, p_key: Any) -> str | None:
        character = getattr(p_key, "char", None)
        if isinstance(character, str) and character:
            return normalizeKeyName(character)

        raw_name = str(p_key)
        if not raw_name:
            return None

        return normalizeKeyName(raw_name)
