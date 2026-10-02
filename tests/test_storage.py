import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soundboard.storage import ApplicationPaths, SoundboardStore


class StorageTests(unittest.TestCase):
    def test_initialization_creates_both_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = ApplicationPaths(Path(temporary_directory))

            first_store = SoundboardStore(paths)
            second_store = SoundboardStore(paths)

            self.assertTrue(paths.getSoundsFile().is_file())
            self.assertTrue(paths.getKeybindsFile().is_file())
            self.assertTrue(first_store.getIsFirstLaunch())
            self.assertFalse(second_store.getIsFirstLaunch())

    def test_import_copies_audio_and_delete_removes_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.wav"
            source.write_bytes(b"RIFF-test-audio")
            store = SoundboardStore(ApplicationPaths(root / "data"))
            record = store.importSound(source, "proc")
            store.assignBinding(record.getSoundId(), ("ctrl", "x"))

            managed_path = store.getSoundPath(record.getSoundId())
            self.assertTrue(managed_path.is_file())
            source.unlink()
            self.assertTrue(managed_path.is_file())

            store.removeSound(record.getSoundId())

            self.assertFalse(managed_path.exists())
            self.assertEqual({}, store.getBindings())

    def test_rename_preserves_binding_to_immutable_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.ogg"
            source.write_bytes(b"OggS-test-audio")
            store = SoundboardStore(ApplicationPaths(root / "data"))
            record = store.importSound(source, "before")
            store.assignBinding(record.getSoundId(), ("f8",))

            store.renameSound(record.getSoundId(), "after")

            self.assertEqual("after", store.getSound(record.getSoundId()).getTag())
            self.assertEqual(record.getSoundId(), store.getBindings()[("f8",)])

    def test_duplicate_tags_and_shortcuts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_source = root / "first.wav"
            second_source = root / "second.wav"
            first_source.write_bytes(b"first")
            second_source.write_bytes(b"second")
            store = SoundboardStore(ApplicationPaths(root / "data"))
            first = store.importSound(first_source, "one")
            second = store.importSound(second_source, "two")
            store.assignBinding(first.getSoundId(), ("ctrl", "x"))

            with self.assertRaisesRegex(ValueError, "already exists"):
                store.renameSound(second.getSoundId(), "ONE")
            with self.assertRaisesRegex(ValueError, "already assigned"):
                store.assignBinding(second.getSoundId(), ("ctrl", "x"))

    def test_malformed_json_is_backed_up_and_recreated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ApplicationPaths(root)
            paths.createDirectories()
            paths.getSoundsFile().write_text("{not-json", encoding="utf-8")
            paths.getKeybindsFile().write_text(
                json.dumps({"schema_version": 99, "keybinds": {}}),
                encoding="utf-8",
            )

            store = SoundboardStore(paths)

            self.assertEqual([], store.getSounds())
            self.assertTrue(list(root.glob("sounds.json.corrupt-*")))
            self.assertTrue(list(root.glob("keybinds.json.corrupt-*")))
            self.assertEqual(1, json.loads(paths.getSoundsFile().read_text())["schema_version"])

    def test_failed_atomic_write_keeps_previous_json_and_removes_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            store = SoundboardStore(ApplicationPaths(root / "data"))
            sounds_file = store.getPaths().getSoundsFile()
            original_json = sounds_file.read_text(encoding="utf-8")

            with patch(
                "soundboard.storage.os.replace",
                side_effect=[None, OSError("disk")],
            ):
                with self.assertRaisesRegex(OSError, "disk"):
                    store.importSound(source, "will-fail")

            self.assertEqual(original_json, sounds_file.read_text(encoding="utf-8"))
            self.assertEqual([], store.getSounds())
            self.assertEqual([], list(store.getPaths().getSoundsDirectory().glob("*.wav")))

    def test_legacy_keybinds_migrate_without_extra_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            paths = ApplicationPaths(root / "data")
            store = SoundboardStore(paths)
            record = store.importSound(source, "legacy")
            paths.getKeybindsFile().write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "keybinds": {"ctrl+x": record.getSoundId()},
                    }
                ),
                encoding="utf-8",
            )

            migrated_store = SoundboardStore(paths)
            migrated_data = json.loads(paths.getKeybindsFile().read_text(encoding="utf-8"))

            self.assertEqual(record.getSoundId(), migrated_store.getBindings()[("ctrl", "x")])
            self.assertEqual(3, migrated_data["schema_version"])
            self.assertNotIn("legacy_metadata", migrated_data)

    def test_schema_two_extra_metadata_is_removed_without_losing_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            paths = ApplicationPaths(root / "data")
            store = SoundboardStore(paths)
            record = store.importSound(source, "legacy")
            paths.getKeybindsFile().write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "keybinds": {"ctrl+x": record.getSoundId()},
                        "legacy_metadata": {
                            record.getSoundId(): {
                                "shortcut_id": "sound_example",
                                "trigger_description": "Ctrl+Shift+X",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            reloaded_store = SoundboardStore(paths)
            migrated_data = json.loads(paths.getKeybindsFile().read_text(encoding="utf-8"))

            self.assertEqual(record.getSoundId(), reloaded_store.getBindings()[("ctrl", "x")])
            self.assertEqual(3, migrated_data["schema_version"])
            self.assertNotIn("legacy_metadata", migrated_data)


if __name__ == "__main__":
    unittest.main()
