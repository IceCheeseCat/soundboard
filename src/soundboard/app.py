from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from soundboard.audio import AudioService
from soundboard.constants import (
    APPLICATION_NAME,
    DEFAULT_SOUND_FILE_NAME,
    DEFAULT_SOUND_TAG,
)
from soundboard.controller import SoundboardController
from soundboard.gui import APPLICATION_STYLE, MainWindow
from soundboard.hotkeys import GlobalHotkeyService
from soundboard.storage import SoundboardStore


def resolveBundledAsset() -> Path | None:
    source_asset = Path(__file__).resolve().parents[2] / "assets" / DEFAULT_SOUND_FILE_NAME
    installed_asset = (
        Path(sys.prefix)
        / "share"
        / "soundboard"
        / "assets"
        / DEFAULT_SOUND_FILE_NAME
    )
    for asset_path in (source_asset, installed_asset):
        if asset_path.is_file():
            return asset_path

    return None


def seedBundledSound(p_store: SoundboardStore, p_assetPath: Path | None) -> None:
    if (
        not p_store.getIsFirstLaunch()
        or p_assetPath is None
        or p_store.findSoundByTag(DEFAULT_SOUND_TAG) is not None
    ):
        return

    p_store.importSound(
        p_assetPath,
        p_tag=DEFAULT_SOUND_TAG,
        p_displayName="Heartsteel Proc",
    )


def main(p_arguments: list[str] | None = None) -> int:
    arguments = p_arguments if p_arguments is not None else sys.argv
    application = QApplication(arguments)
    application.setApplicationName(APPLICATION_NAME)
    application.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    application.setStyleSheet(APPLICATION_STYLE)

    try:
        store = SoundboardStore()
        seedBundledSound(store, resolveBundledAsset())
    except (OSError, ValueError) as error:
        QMessageBox.critical(
            None,
            APPLICATION_NAME,
            f"Unable to initialize application data: {error}",
        )
        return 1
    audio_service = AudioService()
    hotkey_service = GlobalHotkeyService()
    controller = SoundboardController(store, audio_service, hotkey_service)
    window = MainWindow(controller)

    application.aboutToQuit.connect(hotkey_service.stop)
    application.aboutToQuit.connect(audio_service.shutdown)
    window.show()
    hotkey_service.start()
    return application.exec()
