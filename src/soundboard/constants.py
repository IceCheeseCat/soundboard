from typing import Final


APPLICATION_NAME: Final[str] = "Soundboard"
APPLICATION_SLUG: Final[str] = "soundboard"
SOUNDS_FILE_NAME: Final[str] = "sounds.json"
KEYBINDS_FILE_NAME: Final[str] = "keybinds.json"
SOUNDS_DIRECTORY_NAME: Final[str] = "sounds"
SOUNDS_SCHEMA_VERSION: Final[int] = 1
KEYBINDS_SCHEMA_VERSION: Final[int] = 3
SUPPORTED_KEYBINDS_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset({1, 2, 3})
DEFAULT_SOUND_TAG: Final[str] = "heartsteel-proc"
DEFAULT_SOUND_FILE_NAME: Final[str] = "heartsteel-proc.wav"
SUPPORTED_AUDIO_SUFFIXES: Final[set[str]] = {".wav", ".mp3", ".ogg"}
MAX_SHORTCUT_KEYS: Final[int] = 3
HISTORY_FADE_DURATION_MS: Final[int] = 5_000
AUDIO_CHANNEL_COUNT: Final[int] = 32
RANDOM_TAG_BYTES: Final[int] = 3
