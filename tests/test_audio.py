import tempfile
import unittest
from pathlib import Path

from soundboard.audio import AudioService


class FakeSound:
    def __init__(self, p_path: str) -> None:
        self.m_path = p_path
        self.m_playCount = 0

    def getPath(self) -> str:
        return self.m_path

    def setPath(self, p_path: str) -> None:
        self.m_path = p_path

    def getPlayCount(self) -> int:
        return self.m_playCount

    def setPlayCount(self, p_playCount: int) -> None:
        self.m_playCount = p_playCount

    def play(self) -> object:
        self.m_playCount += 1
        return object()


class FakeMixer:
    def __init__(self) -> None:
        self.m_initialized = False
        self.m_channelCount = 0
        self.m_sounds: dict[str, FakeSound] = {}

    def getInitialized(self) -> bool:
        return self.m_initialized

    def setInitialized(self, p_initialized: bool) -> None:
        self.m_initialized = p_initialized

    def getChannelCount(self) -> int:
        return self.m_channelCount

    def setChannelCount(self, p_channelCount: int) -> None:
        self.m_channelCount = p_channelCount

    def getSounds(self) -> dict[str, FakeSound]:
        return dict(self.m_sounds)

    def setSounds(self, p_sounds: dict[str, FakeSound]) -> None:
        self.m_sounds = dict(p_sounds)

    def init(self) -> None:
        self.m_initialized = True

    def set_num_channels(self, p_channelCount: int) -> None:
        self.m_channelCount = p_channelCount

    def Sound(self, p_path: str) -> FakeSound:
        sound = FakeSound(p_path)
        self.m_sounds[p_path] = sound
        return sound

    def stop(self) -> None:
        pass

    def quit(self) -> None:
        self.m_initialized = False


class AudioTests(unittest.TestCase):
    def test_repeated_play_uses_cache_and_allows_multiple_plays(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            audio_path = Path(temporary_directory) / "sound.wav"
            audio_path.write_bytes(b"audio")
            mixer = FakeMixer()
            service = AudioService(mixer)

            service.play(audio_path)
            service.play(audio_path)

            sound = mixer.getSounds()[str(audio_path)]
            self.assertEqual(2, sound.getPlayCount())
            self.assertGreaterEqual(mixer.getChannelCount(), 2)


if __name__ == "__main__":
    unittest.main()

