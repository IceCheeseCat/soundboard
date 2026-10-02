from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from platformdirs import user_data_path

from soundboard.constants import (
    APPLICATION_SLUG,
    KEYBINDS_FILE_NAME,
    KEYBINDS_SCHEMA_VERSION,
    RANDOM_TAG_BYTES,
    SOUNDS_DIRECTORY_NAME,
    SOUNDS_SCHEMA_VERSION,
    SOUNDS_FILE_NAME,
    SUPPORTED_KEYBINDS_SCHEMA_VERSIONS,
    SUPPORTED_AUDIO_SUFFIXES,
)
from soundboard.models import SoundRecord
from soundboard.shortcuts import shortcutFromStorageKey, shortcutToStorageKey


class ApplicationPaths:
    def __init__(self, p_dataDirectory: Path | None = None) -> None:
        data_directory = p_dataDirectory or user_data_path(
            APPLICATION_SLUG,
            appauthor=False,
            ensure_exists=False,
        )

        self.m_dataDirectory = Path(data_directory)
        self.m_soundsFile = self.m_dataDirectory / SOUNDS_FILE_NAME
        self.m_keybindsFile = self.m_dataDirectory / KEYBINDS_FILE_NAME
        self.m_soundsDirectory = self.m_dataDirectory / SOUNDS_DIRECTORY_NAME

    def getDataDirectory(self) -> Path:
        return self.m_dataDirectory

    def setDataDirectory(self, p_dataDirectory: Path) -> None:
        self.m_dataDirectory = Path(p_dataDirectory)

    def getSoundsFile(self) -> Path:
        return self.m_soundsFile

    def setSoundsFile(self, p_soundsFile: Path) -> None:
        self.m_soundsFile = Path(p_soundsFile)

    def getKeybindsFile(self) -> Path:
        return self.m_keybindsFile

    def setKeybindsFile(self, p_keybindsFile: Path) -> None:
        self.m_keybindsFile = Path(p_keybindsFile)

    def getSoundsDirectory(self) -> Path:
        return self.m_soundsDirectory

    def setSoundsDirectory(self, p_soundsDirectory: Path) -> None:
        self.m_soundsDirectory = Path(p_soundsDirectory)

    def createDirectories(self) -> None:
        self.m_soundsDirectory.mkdir(parents=True, exist_ok=True)


class SoundboardStore:
    def __init__(self, p_paths: ApplicationPaths | None = None) -> None:
        self.m_paths = p_paths or ApplicationPaths()
        self.m_sounds: dict[str, SoundRecord] = {}
        self.m_bindings: dict[str, str] = {}
        self.m_isFirstLaunch = not self.m_paths.getSoundsFile().exists()

        self.m_paths.createDirectories()
        self.load()

    def getPaths(self) -> ApplicationPaths:
        return self.m_paths

    def setPaths(self, p_paths: ApplicationPaths) -> None:
        self.m_paths = p_paths

    def getSounds(self) -> list[SoundRecord]:
        return sorted(self.m_sounds.values(), key=lambda sound: sound.getTag().casefold())

    def setSounds(self, p_sounds: list[SoundRecord]) -> None:
        self.m_sounds = {sound.getSoundId(): sound for sound in p_sounds}

    def getBindings(self) -> dict[tuple[str, ...], str]:
        return {
            shortcutFromStorageKey(shortcut): sound_id
            for shortcut, sound_id in self.m_bindings.items()
        }

    def setBindings(self, p_bindings: dict[tuple[str, ...], str]) -> None:
        self.m_bindings = {
            shortcutToStorageKey(shortcut): sound_id
            for shortcut, sound_id in p_bindings.items()
        }

    def getIsFirstLaunch(self) -> bool:
        return self.m_isFirstLaunch

    def setIsFirstLaunch(self, p_isFirstLaunch: bool) -> None:
        self.m_isFirstLaunch = p_isFirstLaunch

    def load(self) -> None:
        sounds_data = self._readJson(
            self.m_paths.getSoundsFile(),
            {"schema_version": SOUNDS_SCHEMA_VERSION, "sounds": []},
        )
        bindings_data = self._readJson(
            self.m_paths.getKeybindsFile(),
            {
                "schema_version": KEYBINDS_SCHEMA_VERSION,
                "keybinds": {},
            },
        )

        try:
            self.m_sounds = self._parseSounds(sounds_data)
        except ValueError:
            self._backupCorruptFile(self.m_paths.getSoundsFile())
            self.m_sounds = {}

        try:
            self.m_bindings = self._parseBindings(bindings_data)
        except ValueError:
            self._backupCorruptFile(self.m_paths.getKeybindsFile())
            self.m_bindings = {}
        self._saveSounds(self.m_sounds)
        self._saveBindings(self.m_bindings)

    def getSound(self, p_soundId: str) -> SoundRecord:
        try:
            return self.m_sounds[p_soundId]
        except KeyError as error:
            raise KeyError(f"Unknown sound ID: {p_soundId}") from error

    def getSoundPath(self, p_soundId: str) -> Path:
        record = self.getSound(p_soundId)
        return self.m_paths.getSoundsDirectory() / record.getFileName()

    def findSoundByTag(self, p_tag: str) -> SoundRecord | None:
        normalized_tag = p_tag.strip().casefold()
        return next(
            (sound for sound in self.m_sounds.values() if sound.getTag().casefold() == normalized_tag),
            None,
        )

    def importSound(
        self,
        p_sourcePath: Path,
        p_tag: str | None = None,
        p_displayName: str | None = None,
    ) -> SoundRecord:
        source_path = Path(p_sourcePath)
        self._validateSource(source_path)
        tag = self._prepareTag(p_tag)
        if self.findSoundByTag(tag) is not None:
            raise ValueError(f'A sound with tag "{tag}" already exists.')

        sound_id = str(uuid.uuid4())
        managed_file_name = f"{sound_id}{source_path.suffix.lower()}"
        managed_path = self.m_paths.getSoundsDirectory() / managed_file_name
        record = SoundRecord(
            p_soundId=sound_id,
            p_tag=tag,
            p_displayName=(p_displayName or source_path.stem).strip(),
            p_fileName=managed_file_name,
        )
        candidate_sounds = dict(self.m_sounds)
        candidate_sounds[sound_id] = record

        self._copyAtomically(source_path, managed_path)
        try:
            self._saveSounds(candidate_sounds)
        except Exception:
            managed_path.unlink(missing_ok=True)
            raise

        self.m_sounds = candidate_sounds
        return record

    def renameSound(self, p_soundId: str, p_newTag: str) -> SoundRecord:
        record = self.getSound(p_soundId)
        tag = self._prepareTag(p_newTag)
        existing = self.findSoundByTag(tag)
        if existing is not None and existing.getSoundId() != p_soundId:
            raise ValueError(f'A sound with tag "{tag}" already exists.')

        old_tag = record.getTag()
        record.setTag(tag)
        try:
            self._saveSounds(self.m_sounds)
        except Exception:
            record.setTag(old_tag)
            raise

        return record

    def removeSound(self, p_soundId: str) -> None:
        record = self.getSound(p_soundId)
        candidate_sounds = dict(self.m_sounds)
        del candidate_sounds[p_soundId]
        candidate_bindings = {
            shortcut: sound_id
            for shortcut, sound_id in self.m_bindings.items()
            if sound_id != p_soundId
        }

        self._saveSounds(candidate_sounds)
        self._saveBindings(candidate_bindings)
        self.m_sounds = candidate_sounds
        self.m_bindings = candidate_bindings
        (self.m_paths.getSoundsDirectory() / record.getFileName()).unlink(missing_ok=True)

    def assignBinding(self, p_soundId: str, p_shortcut: tuple[str, ...]) -> None:
        self.getSound(p_soundId)
        storage_key = shortcutToStorageKey(p_shortcut)
        existing_sound_id = self.m_bindings.get(storage_key)
        if existing_sound_id is not None and existing_sound_id != p_soundId:
            existing_sound = self.getSound(existing_sound_id)
            raise ValueError(
                f"{storage_key} is already assigned to {existing_sound.getTag()}."
            )

        candidate_bindings = {
            shortcut: sound_id
            for shortcut, sound_id in self.m_bindings.items()
            if sound_id != p_soundId
        }
        candidate_bindings[storage_key] = p_soundId
        self._saveBindings(candidate_bindings)
        self.m_bindings = candidate_bindings

    def removeBindingForSound(self, p_soundId: str) -> None:
        self.getSound(p_soundId)
        candidate_bindings = {
            shortcut: sound_id
            for shortcut, sound_id in self.m_bindings.items()
            if sound_id != p_soundId
        }
        self._saveBindings(candidate_bindings)
        self.m_bindings = candidate_bindings

    def getBindingForSound(self, p_soundId: str) -> tuple[str, ...] | None:
        for shortcut, sound_id in self.m_bindings.items():
            if sound_id == p_soundId:
                return shortcutFromStorageKey(shortcut)

        return None

    def _parseSounds(self, p_data: dict[str, Any]) -> dict[str, SoundRecord]:
        if p_data.get("schema_version") != SOUNDS_SCHEMA_VERSION:
            raise ValueError("Unsupported sounds.json schema version.")
        raw_sounds = p_data.get("sounds")
        if not isinstance(raw_sounds, list):
            raise ValueError("sounds.json must contain a sounds list.")

        sounds: dict[str, SoundRecord] = {}
        tags: set[str] = set()
        for raw_sound in raw_sounds:
            if not isinstance(raw_sound, dict):
                raise ValueError("Each sound entry must be an object.")

            record = SoundRecord.fromDictionary(raw_sound)
            normalized_tag = record.getTag().casefold()
            if record.getSoundId() in sounds or normalized_tag in tags:
                raise ValueError("Sound IDs and tags must be unique.")

            sounds[record.getSoundId()] = record
            tags.add(normalized_tag)

        return sounds

    def _parseBindings(
        self,
        p_data: dict[str, Any],
    ) -> dict[str, str]:
        schema_version = p_data.get("schema_version")
        if schema_version not in SUPPORTED_KEYBINDS_SCHEMA_VERSIONS:
            raise ValueError("Unsupported keybinds.json schema version.")
        raw_bindings = p_data.get("keybinds")
        if not isinstance(raw_bindings, dict):
            raise ValueError("keybinds.json must contain a keybinds object.")

        bindings: dict[str, str] = {}
        for shortcut, sound_id in raw_bindings.items():
            if not isinstance(shortcut, str) or not isinstance(sound_id, str):
                raise ValueError("Keybinding keys and sound IDs must be strings.")
            if sound_id not in self.m_sounds:
                continue

            canonical_key = shortcutToStorageKey(shortcutFromStorageKey(shortcut))
            bindings[canonical_key] = sound_id

        return bindings

    def _prepareTag(self, p_tag: str | None) -> str:
        tag = (p_tag or "").strip()
        if not tag:
            tag = f"sound-{secrets.token_hex(RANDOM_TAG_BYTES)}"
        if len(tag) > 64:
            raise ValueError("Tags may contain at most 64 characters.")

        return tag

    def _validateSource(self, p_sourcePath: Path) -> None:
        if not p_sourcePath.is_file():
            raise FileNotFoundError(f"Audio file does not exist: {p_sourcePath}")
        if p_sourcePath.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_AUDIO_SUFFIXES))
            raise ValueError(f"Unsupported audio format. Choose one of: {supported}")

    def _readJson(self, p_path: Path, p_default: dict[str, Any]) -> dict[str, Any]:
        if not p_path.exists():
            return p_default

        try:
            with p_path.open("r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            if not isinstance(data, dict):
                raise ValueError("JSON document must be an object.")
            return data
        except (OSError, ValueError, json.JSONDecodeError):
            self._backupCorruptFile(p_path)
            return p_default

    def _backupCorruptFile(self, p_path: Path) -> None:
        if not p_path.exists():
            return

        backup_path = p_path.with_name(f"{p_path.name}.corrupt-{uuid.uuid4().hex[:8]}")
        shutil.move(p_path, backup_path)

    def _saveSounds(self, p_sounds: dict[str, SoundRecord]) -> None:
        payload = {
            "schema_version": SOUNDS_SCHEMA_VERSION,
            "sounds": [
                sound.toDictionary()
                for sound in sorted(p_sounds.values(), key=lambda item: item.getTag().casefold())
            ],
        }
        self._writeJsonAtomically(self.m_paths.getSoundsFile(), payload)

    def _saveBindings(self, p_bindings: dict[str, str]) -> None:
        payload = {
            "schema_version": KEYBINDS_SCHEMA_VERSION,
            "keybinds": dict(sorted(p_bindings.items())),
        }
        self._writeJsonAtomically(self.m_paths.getKeybindsFile(), payload)

    def _writeJsonAtomically(self, p_path: Path, p_payload: dict[str, Any]) -> None:
        p_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=p_path.parent,
                prefix=f".{p_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file_handle:
                json.dump(p_payload, file_handle, indent=2, ensure_ascii=False)
                file_handle.write("\n")
                file_handle.flush()
                os.fsync(file_handle.fileno())
                temporary_path = Path(file_handle.name)

            os.replace(temporary_path, p_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _copyAtomically(self, p_sourcePath: Path, p_destinationPath: Path) -> None:
        temporary_path = p_destinationPath.with_suffix(f"{p_destinationPath.suffix}.tmp")
        try:
            shutil.copy2(p_sourcePath, temporary_path)
            os.replace(temporary_path, p_destinationPath)
        finally:
            temporary_path.unlink(missing_ok=True)
