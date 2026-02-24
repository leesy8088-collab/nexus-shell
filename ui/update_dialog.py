"""
업데이트 알림 다이얼로그.
새 버전이 있을 때 릴리즈 노트와 다운로드 링크를 보여줌.
"""

import webbrowser

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit,
)
from PySide6.QtCore import Qt


class UpdateDialog(QDialog):
    def __init__(self, new_version: str, download_url: str,
                 release_notes: str, parent=None):
        super().__init__(parent)
        self._download_url = download_url

        self.setWindowTitle("업데이트 알림")
        self.setFixedSize(420, 340)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.setStyleSheet(
            "QDialog { background: #1a1a1a; color: #e0e0e0; }"
            "QLabel { background: transparent; }"
            "QTextEdit { background: #111111; color: #b0b0b0; "
            "  border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; "
            "  padding: 8px; font-size: 13px; }"
            "QPushButton { border: none; border-radius: 8px; "
            "  padding: 10px 20px; font-size: 13px; font-weight: bold; }"
        )

        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 24, 24, 24)
        lo.setSpacing(16)

        # 제목
        title = QLabel(f"새 버전 {new_version} 이 있습니다!")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(title)

        sub = QLabel(f"현재 버전에서 {new_version}(으)로 업데이트할 수 있습니다.")
        sub.setStyleSheet("font-size: 13px; color: #888888;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(sub)

        # 릴리즈 노트
        if release_notes.strip():
            notes_label = QLabel("릴리즈 노트")
            notes_label.setStyleSheet(
                "font-size: 11px; font-weight: 700; letter-spacing: 1px; "
                "color: #6366f1; margin-top: 4px;"
            )
            lo.addWidget(notes_label)

            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setPlainText(release_notes)
            notes.setMaximumHeight(140)
            lo.addWidget(notes)

        lo.addStretch()

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_later = QPushButton("나중에")
        btn_later.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #888888; }"
            "QPushButton:hover { background: #333333; }"
        )
        btn_later.clicked.connect(self.reject)
        btn_row.addWidget(btn_later)

        btn_download = QPushButton("다운로드")
        btn_download.setStyleSheet(
            "QPushButton { background: #6366f1; color: #ffffff; }"
            "QPushButton:hover { background: #818cf8; }"
        )
        btn_download.clicked.connect(self._open_download)
        btn_row.addWidget(btn_download)

        lo.addLayout(btn_row)

    def _open_download(self):
        """브라우저에서 다운로드 페이지 열기."""
        if self._download_url:
            webbrowser.open(self._download_url)
        self.accept()
