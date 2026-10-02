from __future__ import annotations

from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from soundboard.constants import (
    APPLICATION_NAME,
    HISTORY_FADE_DURATION_MS,
)
from soundboard.controller import SoundboardController
from soundboard.shortcuts import (
    ShortcutCaptureState,
    canonicalizeShortcut,
    formatShortcut,
)


WINDOW_MINIMUM_WIDTH = 820
WINDOW_MINIMUM_HEIGHT = 560
HISTORY_MAXIMUM_ENTRIES = 12
NOW_PLAYING_RESET_MS = 900


class ShortcutCaptureDialog(QDialog):
    def __init__(self, p_parent: QWidget | None = None) -> None:
        super().__init__(p_parent)
        self.m_captureState = ShortcutCaptureState()
        self.m_shortcut: tuple[str, ...] | None = None
        self.m_instructionLabel = QLabel("Press 1–3 keys, then release any one of them.")
        self.m_keysLabel = QLabel("Listening…")
        self.m_cancelButton = QPushButton("Cancel")

        self.setWindowTitle("Listen for shortcut")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.m_keysLabel.setObjectName("captureKeys")
        self.m_keysLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.m_cancelButton.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.m_instructionLabel)
        layout.addWidget(self.m_keysLabel)
        layout.addWidget(self.m_cancelButton, alignment=Qt.AlignmentFlag.AlignRight)

    def getCaptureState(self) -> ShortcutCaptureState:
        return self.m_captureState

    def setCaptureState(self, p_captureState: ShortcutCaptureState) -> None:
        self.m_captureState = p_captureState

    def getShortcut(self) -> tuple[str, ...] | None:
        return self.m_shortcut

    def setShortcut(self, p_shortcut: tuple[str, ...] | None) -> None:
        self.m_shortcut = p_shortcut

    def getInstructionLabel(self) -> QLabel:
        return self.m_instructionLabel

    def setInstructionLabel(self, p_label: QLabel) -> None:
        self.m_instructionLabel = p_label

    def getKeysLabel(self) -> QLabel:
        return self.m_keysLabel

    def setKeysLabel(self, p_label: QLabel) -> None:
        self.m_keysLabel = p_label

    def getCancelButton(self) -> QPushButton:
        return self.m_cancelButton

    def setCancelButton(self, p_button: QPushButton) -> None:
        self.m_cancelButton = p_button

    def keyPressEvent(self, p_event: QKeyEvent) -> None:
        if p_event.isAutoRepeat():
            return
        if p_event.key() == Qt.Key.Key_Escape and not self.m_captureState.getPressedKeys():
            self.reject()
            return

        try:
            self.m_captureState.press(self._eventKeyName(p_event))
            self.m_keysLabel.setText(formatShortcut(self.m_captureState.getPressedKeys()))
        except ValueError as error:
            self.m_instructionLabel.setText(str(error))
            self.m_instructionLabel.setObjectName("errorText")

    def keyReleaseEvent(self, p_event: QKeyEvent) -> None:
        if p_event.isAutoRepeat() or not self.m_captureState.getPressedKeys():
            return

        try:
            self.m_shortcut = self.m_captureState.release(self._eventKeyName(p_event))
            self.accept()
        except ValueError as error:
            self.m_instructionLabel.setText(str(error))
            self.m_instructionLabel.setObjectName("errorText")

    def _eventKeyName(self, p_event: QKeyEvent) -> str:
        modifier_names = {
            Qt.Key.Key_Control: "ctrl",
            Qt.Key.Key_Shift: "shift",
            Qt.Key.Key_Alt: "alt",
            Qt.Key.Key_Meta: "meta",
        }
        if p_event.key() in modifier_names:
            return modifier_names[p_event.key()]

        key_name = QKeySequence(p_event.key()).toString().strip().lower()
        if key_name:
            return key_name

        text = p_event.text().strip()
        return text.lower() if text else str(p_event.key())


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.m_nowPlayingLabel = QLabel("Ready")
        self.m_historyLayout = QVBoxLayout()
        self.m_historyEntries: list[QLabel] = []
        self.m_historyAnimations: list[QPropertyAnimation] = []

        title = QLabel("Now playing")
        title.setObjectName("sectionTitle")
        self.m_nowPlayingLabel.setObjectName("nowPlaying")
        self.m_nowPlayingLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.m_historyLayout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        history_title = QLabel("Session history")
        history_title.setObjectName("sectionTitle")
        history_widget = QWidget()
        history_widget.setObjectName("historySurface")
        history_widget.setLayout(self.m_historyLayout)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.m_nowPlayingLabel, stretch=2)
        layout.addWidget(history_title)
        layout.addWidget(history_widget, stretch=3)

    def getNowPlayingLabel(self) -> QLabel:
        return self.m_nowPlayingLabel

    def setNowPlayingLabel(self, p_label: QLabel) -> None:
        self.m_nowPlayingLabel = p_label

    def getHistoryLayout(self) -> QVBoxLayout:
        return self.m_historyLayout

    def setHistoryLayout(self, p_layout: QVBoxLayout) -> None:
        self.m_historyLayout = p_layout

    def getHistoryEntries(self) -> list[QLabel]:
        return list(self.m_historyEntries)

    def setHistoryEntries(self, p_entries: list[QLabel]) -> None:
        self.m_historyEntries = list(p_entries)

    def getHistoryAnimations(self) -> list[QPropertyAnimation]:
        return list(self.m_historyAnimations)

    def setHistoryAnimations(self, p_animations: list[QPropertyAnimation]) -> None:
        self.m_historyAnimations = list(p_animations)

    def addPlayback(self, p_tag: str) -> None:
        self.m_nowPlayingLabel.setText(f"♪  {p_tag}")
        self.m_nowPlayingLabel.setProperty("playing", True)
        self.m_nowPlayingLabel.style().unpolish(self.m_nowPlayingLabel)
        self.m_nowPlayingLabel.style().polish(self.m_nowPlayingLabel)

        QApplication.instance().processEvents()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(NOW_PLAYING_RESET_MS, self._resetNowPlaying)

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = QLabel(f"{timestamp}   {p_tag}")
        entry.setObjectName("historyEntry")
        opacity_effect = QGraphicsOpacityEffect(entry)
        entry.setGraphicsEffect(opacity_effect)
        self.m_historyLayout.addWidget(entry)
        self.m_historyEntries.append(entry)

        animation = QPropertyAnimation(opacity_effect, b"opacity", self)
        animation.setDuration(HISTORY_FADE_DURATION_MS)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.InCubic)
        animation.finished.connect(lambda: self._removeHistoryEntry(entry, animation))
        self.m_historyAnimations.append(animation)
        animation.start()

        while len(self.m_historyEntries) > HISTORY_MAXIMUM_ENTRIES:
            self._removeHistoryEntry(self.m_historyEntries[0], None)

    def _resetNowPlaying(self) -> None:
        self.m_nowPlayingLabel.setText("Ready")
        self.m_nowPlayingLabel.setProperty("playing", False)
        self.m_nowPlayingLabel.style().unpolish(self.m_nowPlayingLabel)
        self.m_nowPlayingLabel.style().polish(self.m_nowPlayingLabel)

    def _removeHistoryEntry(
        self,
        p_entry: QLabel,
        p_animation: QPropertyAnimation | None,
    ) -> None:
        if p_entry in self.m_historyEntries:
            self.m_historyEntries.remove(p_entry)
            self.m_historyLayout.removeWidget(p_entry)
            p_entry.deleteLater()
        if p_animation is not None and p_animation in self.m_historyAnimations:
            self.m_historyAnimations.remove(p_animation)
            p_animation.deleteLater()


class LibraryPage(QWidget):
    def __init__(self, p_controller: SoundboardController) -> None:
        super().__init__()
        self.m_controller = p_controller
        self.m_table = self._createTable()
        self.m_addButton = QPushButton("Add sound")
        self.m_renameButton = QPushButton("Rename tag")
        self.m_previewButton = QPushButton("Play")
        self.m_deleteButton = QPushButton("Delete")

        self.m_addButton.setObjectName("primaryButton")
        self.m_deleteButton.setObjectName("dangerButton")
        self.m_addButton.clicked.connect(self._addSound)
        self.m_renameButton.clicked.connect(self._renameSound)
        self.m_previewButton.clicked.connect(self._previewSound)
        self.m_deleteButton.clicked.connect(self._deleteSound)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.m_addButton)
        button_layout.addWidget(self.m_renameButton)
        button_layout.addWidget(self.m_previewButton)
        button_layout.addStretch()
        button_layout.addWidget(self.m_deleteButton)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sound library"), alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.m_table)
        layout.addLayout(button_layout)
        self.refresh()

    def getController(self) -> SoundboardController:
        return self.m_controller

    def setController(self, p_controller: SoundboardController) -> None:
        self.m_controller = p_controller

    def getTable(self) -> QTableWidget:
        return self.m_table

    def setTable(self, p_table: QTableWidget) -> None:
        self.m_table = p_table

    def getAddButton(self) -> QPushButton:
        return self.m_addButton

    def setAddButton(self, p_button: QPushButton) -> None:
        self.m_addButton = p_button

    def getRenameButton(self) -> QPushButton:
        return self.m_renameButton

    def setRenameButton(self, p_button: QPushButton) -> None:
        self.m_renameButton = p_button

    def getPreviewButton(self) -> QPushButton:
        return self.m_previewButton

    def setPreviewButton(self, p_button: QPushButton) -> None:
        self.m_previewButton = p_button

    def getDeleteButton(self) -> QPushButton:
        return self.m_deleteButton

    def setDeleteButton(self, p_button: QPushButton) -> None:
        self.m_deleteButton = p_button

    def refresh(self) -> None:
        sounds = self.m_controller.getStore().getSounds()
        self.m_table.setRowCount(len(sounds))
        for row, sound in enumerate(sounds):
            tag_item = QTableWidgetItem(sound.getTag())
            tag_item.setData(Qt.ItemDataRole.UserRole, sound.getSoundId())
            self.m_table.setItem(row, 0, tag_item)
            self.m_table.setItem(row, 1, QTableWidgetItem(sound.getDisplayName()))
            self.m_table.setItem(row, 2, QTableWidgetItem(sound.getFileName()))

    def _createTable(self) -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Tag", "Name", "Managed file"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _selectedSoundId(self) -> str | None:
        selected_rows = self.m_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        item = self.m_table.item(selected_rows[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _addSound(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add sound",
            "",
            "Audio files (*.wav *.mp3 *.ogg)",
        )
        if not file_path:
            return

        tag, accepted = QInputDialog.getText(
            self,
            "Sound tag",
            "Unique tag (leave blank to generate one):",
        )
        if not accepted:
            return

        self._showOperationError(lambda: self.m_controller.importSound(Path(file_path), tag))

    def _renameSound(self) -> None:
        sound_id = self._selectedSoundId()
        if sound_id is None:
            self._showSelectionMessage()
            return

        record = self.m_controller.getStore().getSound(sound_id)
        tag, accepted = QInputDialog.getText(
            self,
            "Rename tag",
            "New unique tag:",
            text=record.getTag(),
        )
        if accepted:
            self._showOperationError(lambda: self.m_controller.renameSound(sound_id, tag))

    def _previewSound(self) -> None:
        sound_id = self._selectedSoundId()
        if sound_id is None:
            self._showSelectionMessage()
            return

        self.m_controller.playSound(sound_id)

    def _deleteSound(self) -> None:
        sound_id = self._selectedSoundId()
        if sound_id is None:
            self._showSelectionMessage()
            return

        record = self.m_controller.getStore().getSound(sound_id)
        response = QMessageBox.question(
            self,
            "Delete sound",
            f'Delete "{record.getTag()}" and all of its keybindings?',
        )
        if response == QMessageBox.StandardButton.Yes:
            self._showOperationError(lambda: self.m_controller.removeSound(sound_id))

    def _showSelectionMessage(self) -> None:
        QMessageBox.information(self, APPLICATION_NAME, "Select a sound first.")

    def _showOperationError(self, p_operation: Callable[[], object]) -> None:
        try:
            p_operation()
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.critical(self, APPLICATION_NAME, str(error))


class BindingsPage(QWidget):
    def __init__(self, p_controller: SoundboardController) -> None:
        super().__init__()
        self.m_controller = p_controller
        self.m_table = self._createTable()
        self.m_listenButton = QPushButton("Listen")
        self.m_removeButton = QPushButton("Remove binding")
        self.m_statusLabel = QLabel()

        self._updateStatus(p_controller.getHotkeyService().getStatusMessage())
        self.m_listenButton.setObjectName("primaryButton")
        self.m_listenButton.clicked.connect(self._listen)
        self.m_removeButton.clicked.connect(self._removeBinding)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.m_listenButton)
        button_layout.addWidget(self.m_removeButton)
        button_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.m_statusLabel)
        layout.addWidget(self.m_table)
        layout.addLayout(button_layout)
        self.refresh()

    def getController(self) -> SoundboardController:
        return self.m_controller

    def setController(self, p_controller: SoundboardController) -> None:
        self.m_controller = p_controller

    def getTable(self) -> QTableWidget:
        return self.m_table

    def setTable(self, p_table: QTableWidget) -> None:
        self.m_table = p_table

    def getListenButton(self) -> QPushButton:
        return self.m_listenButton

    def setListenButton(self, p_button: QPushButton) -> None:
        self.m_listenButton = p_button

    def getRemoveButton(self) -> QPushButton:
        return self.m_removeButton

    def setRemoveButton(self, p_button: QPushButton) -> None:
        self.m_removeButton = p_button

    def getStatusLabel(self) -> QLabel:
        return self.m_statusLabel

    def setStatusLabel(self, p_label: QLabel) -> None:
        self.m_statusLabel = p_label

    def refresh(self) -> None:
        store = self.m_controller.getStore()
        sounds = store.getSounds()
        self.m_table.setRowCount(len(sounds))
        for row, sound in enumerate(sounds):
            shortcut = store.getBindingForSound(sound.getSoundId())
            shortcut_text = formatShortcut(shortcut) if shortcut else "Not assigned"
            tag_item = QTableWidgetItem(sound.getTag())
            tag_item.setData(Qt.ItemDataRole.UserRole, sound.getSoundId())
            self.m_table.setItem(row, 0, tag_item)
            self.m_table.setItem(
                row,
                1,
                QTableWidgetItem(shortcut_text),
            )

    def _createTable(self) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Sound tag", "Shortcut"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _selectedSoundId(self) -> str | None:
        selected_rows = self.m_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        item = self.m_table.item(selected_rows[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _listen(self) -> None:
        hotkey_service = self.m_controller.getHotkeyService()

        sound_id = self._selectedSoundId()
        if sound_id is None:
            QMessageBox.information(self, APPLICATION_NAME, "Select a sound first.")
            return

        hotkey_service.setIsSuppressed(True)
        try:
            dialog = ShortcutCaptureDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            shortcut = dialog.getShortcut()
            if shortcut is None:
                return

            self.m_controller.assignBinding(sound_id, canonicalizeShortcut(shortcut))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, APPLICATION_NAME, str(error))
        finally:
            hotkey_service.setIsSuppressed(False)

    def _updateStatus(self, p_message: str) -> None:
        is_warning = "unavailable" in p_message.casefold() or "x11" in p_message.casefold()
        self.m_statusLabel.setText(p_message)
        self.m_statusLabel.setObjectName("statusWarning" if is_warning else "statusOk")
        self.m_statusLabel.style().unpolish(self.m_statusLabel)
        self.m_statusLabel.style().polish(self.m_statusLabel)

    def _removeBinding(self) -> None:
        sound_id = self._selectedSoundId()
        if sound_id is None:
            QMessageBox.information(self, APPLICATION_NAME, "Select a sound first.")
            return

        try:
            self.m_controller.removeBinding(sound_id)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, APPLICATION_NAME, str(error))


class MainWindow(QMainWindow):
    def __init__(self, p_controller: SoundboardController) -> None:
        super().__init__()
        self.m_controller = p_controller
        self.m_dashboardPage = DashboardPage()
        self.m_libraryPage = LibraryPage(p_controller)
        self.m_bindingsPage = BindingsPage(p_controller)
        self.m_pageStack = QStackedWidget()
        self.m_trayIcon = QSystemTrayIcon(self)
        self.m_forceQuit = False

        self.setWindowTitle(APPLICATION_NAME)
        self.setMinimumSize(WINDOW_MINIMUM_WIDTH, WINDOW_MINIMUM_HEIGHT)
        self._buildInterface()
        self._buildTrayIcon()
        self._connectSignals()

    def getController(self) -> SoundboardController:
        return self.m_controller

    def setController(self, p_controller: SoundboardController) -> None:
        self.m_controller = p_controller

    def getDashboardPage(self) -> DashboardPage:
        return self.m_dashboardPage

    def setDashboardPage(self, p_page: DashboardPage) -> None:
        self.m_dashboardPage = p_page

    def getLibraryPage(self) -> LibraryPage:
        return self.m_libraryPage

    def setLibraryPage(self, p_page: LibraryPage) -> None:
        self.m_libraryPage = p_page

    def getBindingsPage(self) -> BindingsPage:
        return self.m_bindingsPage

    def setBindingsPage(self, p_page: BindingsPage) -> None:
        self.m_bindingsPage = p_page

    def getPageStack(self) -> QStackedWidget:
        return self.m_pageStack

    def setPageStack(self, p_pageStack: QStackedWidget) -> None:
        self.m_pageStack = p_pageStack

    def getTrayIcon(self) -> QSystemTrayIcon:
        return self.m_trayIcon

    def setTrayIcon(self, p_trayIcon: QSystemTrayIcon) -> None:
        self.m_trayIcon = p_trayIcon

    def getForceQuit(self) -> bool:
        return self.m_forceQuit

    def setForceQuit(self, p_forceQuit: bool) -> None:
        self.m_forceQuit = p_forceQuit

    def closeEvent(self, p_event: QCloseEvent) -> None:
        if self.m_forceQuit or not self.m_trayIcon.isVisible():
            p_event.accept()
            return

        p_event.ignore()
        self.hide()
        self.m_trayIcon.showMessage(
            APPLICATION_NAME,
            "Still running in the system tray.",
            QSystemTrayIcon.MessageIcon.Information,
            2_000,
        )

    def quitApplication(self) -> None:
        self.m_forceQuit = True
        self.m_controller.getHotkeyService().stop()
        self.m_controller.getAudioService().shutdown()
        self.m_trayIcon.hide()
        QApplication.instance().quit()

    def _buildInterface(self) -> None:
        self.m_pageStack.addWidget(self.m_dashboardPage)
        self.m_pageStack.addWidget(self.m_libraryPage)
        self.m_pageStack.addWidget(self.m_bindingsPage)

        home_button = QPushButton("Home")
        library_button = QPushButton("Sound library")
        bindings_button = QPushButton("Keybindings")
        for button in (home_button, library_button, bindings_button):
            button.setObjectName("navigationButton")

        home_button.clicked.connect(lambda: self.m_pageStack.setCurrentIndex(0))
        library_button.clicked.connect(lambda: self.m_pageStack.setCurrentIndex(1))
        bindings_button.clicked.connect(lambda: self.m_pageStack.setCurrentIndex(2))

        navigation = QVBoxLayout()
        brand = QLabel("SOUNDBOARD")
        brand.setObjectName("brand")
        navigation.addWidget(brand)
        navigation.addWidget(home_button)
        navigation.addWidget(library_button)
        navigation.addWidget(bindings_button)
        navigation.addStretch()

        navigation_widget = QWidget()
        navigation_widget.setObjectName("navigation")
        navigation_widget.setLayout(navigation)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(navigation_widget)
        content_layout.addWidget(self.m_pageStack, stretch=1)

        central_widget = QWidget()
        central_widget.setLayout(content_layout)
        self.setCentralWidget(central_widget)

    def _buildTrayIcon(self) -> None:
        self.m_trayIcon.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        )
        self.m_trayIcon.setToolTip(APPLICATION_NAME)
        tray_menu = self.m_trayIcon.contextMenu()
        if tray_menu is None:
            from PySide6.QtWidgets import QMenu

            tray_menu = QMenu(self)

        show_action = QAction("Show", self)
        quit_action = QAction("Quit", self)
        show_action.triggered.connect(self._showFromTray)
        quit_action.triggered.connect(self.quitApplication)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.m_trayIcon.setContextMenu(tray_menu)
        self.m_trayIcon.activated.connect(self._trayActivated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.m_trayIcon.show()

    def _connectSignals(self) -> None:
        self.m_controller.getLibraryChangedSignal().connect(self._refreshPages)
        self.m_controller.getPlaybackOccurredSignal().connect(self.m_dashboardPage.addPlayback)
        self.m_controller.getErrorOccurredSignal().connect(self._showBackgroundError)
        self.m_controller.getHotkeyService().getListenerErrorSignal().connect(
            self._showBackgroundError
        )

    def _refreshPages(self) -> None:
        self.m_libraryPage.refresh()
        self.m_bindingsPage.refresh()

    def _showFromTray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _trayActivated(self, p_reason: QSystemTrayIcon.ActivationReason) -> None:
        if p_reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._showFromTray()

    def _showBackgroundError(self, p_message: str) -> None:
        if self.isVisible():
            QMessageBox.warning(self, APPLICATION_NAME, p_message)
        elif self.m_trayIcon.isVisible():
            self.m_trayIcon.showMessage(
                APPLICATION_NAME,
                p_message,
                QSystemTrayIcon.MessageIcon.Warning,
                4_000,
            )


APPLICATION_STYLE = """
QWidget {
    background: #11151d;
    color: #f2f0e6;
    font-size: 14px;
}
QWidget#navigation {
    background: #171d28;
    min-width: 190px;
    max-width: 190px;
}
QLabel#brand {
    color: #d6b45f;
    font-size: 20px;
    font-weight: 700;
    padding: 24px 12px;
}
QPushButton {
    background: #252d3a;
    border: 1px solid #394455;
    border-radius: 6px;
    padding: 9px 14px;
}
QPushButton:hover { background: #303a49; }
QPushButton#navigationButton {
    text-align: left;
    border: 0;
    background: transparent;
    padding: 12px;
}
QPushButton#navigationButton:hover { background: #252d3a; }
QPushButton#primaryButton { background: #876f32; border-color: #d6b45f; }
QPushButton#dangerButton { color: #ffb4ab; }
QLabel#sectionTitle { color: #aeb8c7; font-size: 16px; }
QLabel#nowPlaying {
    background: #171d28;
    border: 1px solid #394455;
    border-radius: 14px;
    color: #aeb8c7;
    font-size: 30px;
}
QLabel#nowPlaying[playing="true"] { color: #f0ce72; border-color: #d6b45f; }
QWidget#historySurface { background: #171d28; border-radius: 10px; }
QLabel#historyEntry { padding: 6px 10px; color: #d6b45f; }
QLabel#captureKeys { color: #f0ce72; font-size: 24px; padding: 28px; }
QLabel#errorText, QLabel#statusWarning { color: #ffb4ab; }
QLabel#statusOk { color: #8bd7a4; }
QTableWidget {
    background: #171d28;
    alternate-background-color: #1d2430;
    border: 1px solid #394455;
    gridline-color: #2b3442;
    selection-background-color: #5a4a25;
}
QHeaderView::section {
    background: #252d3a;
    color: #f2f0e6;
    border: 0;
    padding: 8px;
}
"""
