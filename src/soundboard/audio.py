from __future__ import annotations

from pathlib import Path
from typing import Any

from soundboard.constants import AUDIO_CHANNEL_COUNT


class AudioService:
    def __init__(self, p_mixer: Any | None = None) -> None:
        if p_mixer is None:
            from pygame import mixer

            p_mixer = mixer

        self.m_mixer = p_mixer
        self.m_soundCache: dict[Path, Any] = {}
        self.m_isInitialized = False

    def getMixer(self) -> Any:
        return self.m_mixer

    def setMixer(self, p_mixer: Any) -> None:
        self.stopAll()
        self.m_mixer = p_mixer
        self.m_soundCache = {}
        self.m_isInitialized = False

    def getSoundCache(self) -> dict[Path, Any]:
        return dict(self.m_soundCache)

    def setSoundCache(self, p_soundCache: dict[Path, Any]) -> None:
        self.m_soundCache = dict(p_soundCache)

    def getIsInitialized(self) -> bool:
        return self.m_isInitialized

    def setIsInitialized(self, p_isInitialized: bool) -> None:
        self.m_isInitialized = p_isInitialized

    def play(self, p_audioPath: Path) -> None:
        audio_path = Path(p_audioPath)
        if not audio_path.is_file():
            raise FileNotFoundError(f"Managed audio file is missing: {audio_path}")

        try:
            self._initialize()
            sound = self.m_soundCache.get(audio_path)
            if sound is None:
                sound = self.m_mixer.Sound(str(audio_path))
                self.m_soundCache[audio_path] = sound

            channel = sound.play()
            if channel is None:
                raise RuntimeError("No audio mixer channel is available.")
        except Exception as error:
            if isinstance(error, RuntimeError):
                raise
            raise RuntimeError(f"Unable to play {audio_path.name}: {error}") from error

    def removeFromCache(self, p_audioPath: Path) -> None:
        self.m_soundCache.pop(Path(p_audioPath), None)

    def stopAll(self) -> None:
        if self.m_isInitialized:
            self.m_mixer.stop()

    def shutdown(self) -> None:
        if not self.m_isInitialized:
            return

        self.m_mixer.stop()
        self.m_mixer.quit()
        self.m_isInitialized = False
        self.m_soundCache = {}

    def _initialize(self) -> None:
        if self.m_isInitialized:
            return

        self.m_mixer.init()
        self.m_mixer.set_num_channels(AUDIO_CHANNEL_COUNT)
        self.m_isInitialized = True
