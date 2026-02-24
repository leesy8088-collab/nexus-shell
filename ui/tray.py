"""
TrayManager: 시스템 트레이 아이콘 + 우클릭 메뉴
"""

import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, Signal

from config import BUNDLE_DIR


class TrayManager(QObject):
    open_requested = Signal()
    settings_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        icon_path = os.path.join(BUNDLE_DIR, "assets", "icon.png")
        icon = QIcon(icon_path)

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip("Nexus Shell")

        # 우클릭 메뉴
        menu = QMenu()
        open_action = QAction("열기 (Alt+Space)", menu)
        open_action.triggered.connect(self.open_requested)
        menu.addAction(open_action)

        menu.addSeparator()

        settings_action = QAction("설정", menu)
        settings_action.triggered.connect(self.settings_requested)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("종료", menu)
        quit_action.triggered.connect(self.exit_requested)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

        # 더블클릭 → Spotlight 열기
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
