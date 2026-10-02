from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from soundboard.audio import AudioService
from soundboard.hotkeys import GlobalHotkeyService
from soundboard.models import SoundRecord
from soundboard.storage import SoundboardStore


class SoundboardController(QObject):
    m_libraryChanged = Signal()
    m_playbackOccurred = Signal(str)
    m_errorOccurred = Signal(str)

    def __init__(
        self,
        p_store: SoundboardStore,
        p_audioService: AudioService,
        p_hotkeyService: GlobalHotkeyService,
    ) -> None:
        super().__init__()
        self.m_store = p_store
        self.m_audioService = p_audioService
        self.m_hotkeyService = p_hotkeyService

        self.m_hotkeyService.getSoundTriggeredSignal().connect(self.playSound)
        self._refreshBindings()

    def getLibraryChangedSignal(self) -> Signal:
        return self.m_libraryChanged

    def getPlaybackOccurredSignal(self) -> Signal:
        return self.m_playbackOccurred

    def getErrorOccurredSignal(self) -> Signal:
        return self.m_errorOccurred

    def getStore(self) -> SoundboardStore:
        return self.m_store

    def setStore(self, p_store: SoundboardStore) -> None:
        self.m_store = p_store
        self._refreshBindings()

    def getAudioService(self) -> AudioService:
        return self.m_audioService

    def setAudioService(self, p_audioService: AudioService) -> None:
        self.m_audioService = p_audioService

    def getHotkeyService(self) -> GlobalHotkeyService:
        return self.m_hotkeyService

    def setHotkeyService(
        self,
        p_hotkeyService: GlobalHotkeyService,
    ) -> None:
        self.m_hotkeyService = p_hotkeyService
        self._refreshBindings()

    def importSound(self, p_sourcePath: Path, p_tag: str | None = None) -> SoundRecord:
        record = self.m_store.importSound(p_sourcePath, p_tag)
        self._refreshBindings()
        self.m_libraryChanged.emit()
        return record

    def renameSound(self, p_soundId: str, p_tag: str) -> SoundRecord:
        record = self.m_store.renameSound(p_soundId, p_tag)
        self._refreshBindings()
        self.m_libraryChanged.emit()
        return record

    def removeSound(self, p_soundId: str) -> None:
        audio_path = self.m_store.getSoundPath(p_soundId)
        self.m_audioService.removeFromCache(audio_path)
        self.m_store.removeSound(p_soundId)
        self._refreshBindings()
        self.m_libraryChanged.emit()

    def assignBinding(self, p_soundId: str, p_shortcut: tuple[str, ...]) -> None:
        self.m_store.assignBinding(p_soundId, p_shortcut)
        self._refreshBindings()
        self.m_libraryChanged.emit()

    def removeBinding(self, p_soundId: str) -> None:
        self.m_store.removeBindingForSound(p_soundId)
        self._refreshBindings()
        self.m_libraryChanged.emit()

    def playSound(self, p_soundId: str) -> None:
        try:
            record = self.m_store.getSound(p_soundId)
            self.m_audioService.play(self.m_store.getSoundPath(p_soundId))
            self.m_playbackOccurred.emit(record.getTag())
        except (KeyError, OSError, RuntimeError, ValueError) as error:
            self.m_errorOccurred.emit(str(error))

    def _refreshBindings(self) -> None:
        self.m_hotkeyService.setBindings(self.m_store.getBindings())
