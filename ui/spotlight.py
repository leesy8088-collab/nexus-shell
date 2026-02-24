"""
SpotlightWindow: 프레임리스 입력창 + 결과 표시 + 녹음 모드
"""

import os
import ctypes
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QProgressBar, QMenu, QApplication, QPushButton,
    QScrollArea,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QSize, QEvent,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPainterPath, QGuiApplication, QPixmap, QCursor,
    QImage,
)

from config import (
    SPOTLIGHT_WIDTH, SPOTLIGHT_INPUT_HEIGHT, RESULT_AUTO_CLOSE_MS,
    DEFAULT_PREFS,
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """'#6366f1' → (99, 102, 241)"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class SpotlightWindow(QWidget):
    input_submitted = Signal(str)
    recording_cancel_requested = Signal()
    history_prev_requested = Signal(str)
    history_next_requested = Signal()
    favorite_clicked = Signal(dict)
    favorite_add_requested = Signal()
    favorite_remove_requested = Signal(str)
    clipboard_item_clicked = Signal(str)           # item_id → 재복사 요청
    clipboard_item_remove_requested = Signal(str)  # item_id → 삭제
    window_clicked = Signal(int)                    # hwnd → 창 포커스 요청

    def __init__(self, parent=None, preferences: dict | None = None):
        super().__init__(parent)

        self._prefs = dict(preferences or DEFAULT_PREFS)
        self._preview_mode = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self._prefs.get("spotlight_width", SPOTLIGHT_WIDTH))

        self._is_recording = False
        self._app_filter_installed = False
        self._animating_out = False

        # 애니메이션
        self._anim_group = None

        # 자동 닫힘 타이머
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._dismiss)

        # 녹음 인디케이터 깜박임 타이머
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_visible = True

        # 즐겨찾기 키보드 탐색 상태
        self._fav_selected = -1     # -1 = 입력창, 0..N = 즐겨찾기/추가 버튼
        self._fav_data: list[dict] = []
        self._fav_widgets: list[QWidget] = []

        # 클립보드 탭 상태
        self._current_tab = "fav"  # "fav" | "clip"
        self._clip_data: list[dict] = []
        self._clip_widgets: list[QWidget] = []

        # 열린 창 상태 (즐겨찾기 아래에 표시)
        self._win_data: list[dict] = []
        self._win_widgets: list[QWidget] = []
        self._win_selected = -1  # -1 = 미선택, 0..N = 창 항목
        self._nav_zone = "fav"   # "fav" | "win" (즐겨찾기 탭 내 탐색 영역)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # 입력 필드
        self._input = QLineEdit()
        self._input.setPlaceholderText("무엇이든 말씀하세요...")
        self._input.setFixedHeight(SPOTLIGHT_INPUT_HEIGHT)
        self._input.returnPressed.connect(self._on_submit)
        layout.addWidget(self._input)

        # ── 탭 바 ──
        self._tab_bar = QWidget()
        self._tab_bar.setObjectName("TabBar")
        self._tab_bar.setStyleSheet("QWidget#TabBar { background: transparent; }")
        tab_layout = QHBoxLayout(self._tab_bar)
        tab_layout.setContentsMargins(4, 0, 4, 0)
        tab_layout.setSpacing(4)

        self._tab_fav = QPushButton("⭐ 즐겨찾기")
        self._tab_clip = QPushButton("📋 클립보드")
        for btn in (self._tab_fav, self._tab_clip):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
        self._tab_fav.clicked.connect(lambda: self._switch_tab("fav"))
        self._tab_clip.clicked.connect(lambda: self._switch_tab("clip"))

        tab_layout.addWidget(self._tab_fav)
        tab_layout.addWidget(self._tab_clip)
        tab_layout.addStretch()
        self._tab_bar.hide()
        layout.addWidget(self._tab_bar)

        # 즐겨찾기 패널 (초기 숨김)
        self._favorites_panel = QWidget()
        self._favorites_panel.setObjectName("FavPanel")
        self._favorites_grid = QGridLayout(self._favorites_panel)
        self._favorites_grid.setContentsMargins(12, 12, 12, 12)
        self._favorites_grid.setSpacing(8)
        self._favorites_panel.hide()
        layout.addWidget(self._favorites_panel)

        # ── 열린 창 패널 (그리드, 즐겨찾기 바로 아래) ──
        self._windows_panel = QWidget()
        self._windows_panel.setObjectName("WinPanel")
        self._windows_grid_layout = QVBoxLayout(self._windows_panel)
        self._windows_grid_layout.setContentsMargins(10, 6, 10, 10)
        self._windows_grid_layout.setSpacing(4)

        self._windows_panel.hide()
        layout.addWidget(self._windows_panel)

        # ── 클립보드 패널 (스크롤 영역) ──
        self._clipboard_scroll = QScrollArea()
        self._clipboard_scroll.setWidgetResizable(True)
        self._clipboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._clipboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._clipboard_scroll.setMaximumHeight(350)

        self._clipboard_panel = QWidget()
        self._clipboard_panel.setObjectName("ClipPanel")
        self._clipboard_panel.setStyleSheet(
            "QWidget#ClipPanel { background: transparent; }"
        )
        self._clipboard_layout = QVBoxLayout(self._clipboard_panel)
        self._clipboard_layout.setContentsMargins(8, 8, 8, 8)
        self._clipboard_layout.setSpacing(4)
        self._clipboard_layout.addStretch()

        self._clipboard_scroll.setWidget(self._clipboard_panel)
        self._clipboard_scroll.hide()
        layout.addWidget(self._clipboard_scroll)

        # 녹음 상태 라벨 (초기 숨김)
        self._recording_label = QLabel()
        self._recording_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._recording_label.hide()
        layout.addWidget(self._recording_label)

        # 음량 바 (초기 숨김)
        self._level_bar = QProgressBar()
        self._level_bar.setRange(0, 100)
        self._level_bar.setValue(0)
        self._level_bar.setTextVisible(False)
        self._level_bar.setFixedHeight(6)
        self._level_bar.hide()
        layout.addWidget(self._level_bar)

        # 결과 라벨 (초기 숨김)
        self._result = QLabel()
        self._result.setWordWrap(True)
        self._result.hide()
        layout.addWidget(self._result)

        # 테마 적용
        self._apply_theme()

    def _apply_theme(self):
        """preferences 기반 스타일 일괄 적용."""
        opacity = self._prefs.get("spotlight_opacity", 230)
        accent = self._prefs.get("accent_color", "#6366f1")
        ar, ag, ab = _hex_to_rgb(accent)

        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background: rgba(30, 30, 30, {opacity});
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                padding: 0 20px;
                font-size: 18px;
                selection-background-color: #4a90d9;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba({ar}, {ag}, {ab}, 0.6);
            }}
            """
        )

        panel_bg = f"rgba(30, 30, 30, {max(opacity - 10, 0)})"
        for panel_name, panel in [
            ("FavPanel", self._favorites_panel),
            ("WinPanel", self._windows_panel),
        ]:
            panel.setStyleSheet(
                f"""
                QWidget#{panel_name} {{
                    background: {panel_bg};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 10px;
                }}
                """
            )

        self._clipboard_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: {panel_bg};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 4px 1px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            """
        )

        self._recording_label.setStyleSheet(
            f"""
            QLabel {{
                background: {panel_bg};
                color: #ff6b6b;
                border: 1px solid rgba(255, 100, 100, 0.3);
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 16px;
            }}
            """
        )

        self._level_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {accent}, stop:0.5 rgba({ar}, {ag}, {ab}, 0.7), stop:1 #f472b6);
                border-radius: 3px;
            }}
            """
        )

        self._result.setStyleSheet(
            f"""
            QLabel {{
                background: {panel_bg};
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 14px;
                line-height: 1.4;
            }}
            """
        )

        # 탭 스타일 업데이트
        self._TAB_STYLE_ACTIVE = (
            f"QPushButton {{ background: rgba({ar}, {ag}, {ab}, 0.45); color: #ffffff; "
            f"border: none; border-bottom: 2px solid rgba({ar}, {ag}, {ab}, 0.7); border-radius: 6px; "
            f"padding: 4px 12px; font-size: 12px; font-weight: bold; }}"
        )
        self._TAB_STYLE_INACTIVE = (
            f"QPushButton {{ background: rgba(30, 30, 30, 200); color: #aaa; "
            f"border: none; border-radius: 6px; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ color: #ddd; background: rgba(50, 50, 50, 220); }}"
        )

        # 선택 하이라이트 스타일
        self._FAV_STYLE_SELECTED = (
            f"QWidget {{ background: rgba({ar}, {ag}, {ab}, 0.25); "
            f"border: 1px solid rgba({ar}, {ag}, {ab}, 0.5); border-radius: 8px; }}"
        )
        self._CLIP_STYLE_SELECTED = (
            f"QWidget {{ background: rgba({ar}, {ag}, {ab}, 0.25); "
            f"border: 1px solid rgba({ar}, {ag}, {ab}, 0.5); border-radius: 8px; }}"
        )
        self._WIN_STYLE_SELECTED = (
            f"QWidget {{ background: rgba({ar}, {ag}, {ab}, 0.25); "
            f"border: 1px solid rgba({ar}, {ag}, {ab}, 0.5); border-radius: 8px; }}"
        )

        if self._tab_bar.isVisible():
            self._update_tab_styles()

    def update_preferences(self, prefs: dict):
        """런타임에 preferences 변경 반영."""
        self._prefs = dict(prefs)
        self.setFixedWidth(prefs.get("spotlight_width", SPOTLIGHT_WIDTH))
        self._apply_theme()
        # 미리보기 모드 중이면 위치도 갱신
        if self._preview_mode and self.isVisible():
            screen = QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                pos_pct = self._prefs.get("spotlight_position", 22) / 100.0
                y = geo.y() + int(geo.height() * pos_pct)
                self.move(x, y)

    def show_preview(self):
        """미리보기 모드로 Spotlight 표시 (설정 창과 공존)."""
        self._preview_mode = True
        self._auto_close_timer.stop()
        self._result.hide()
        self._recording_label.hide()
        self._input.clear()
        self._input.setPlaceholderText("미리보기...")
        self._input.setEnabled(False)

        # 탭/패널 숨김 — 깔끔한 미리보기
        self._tab_bar.hide()
        self._favorites_panel.hide()
        self._clipboard_scroll.hide()
        self._windows_panel.hide()
        self._input.show()
        self.adjustSize()

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            pos_pct = self._prefs.get("spotlight_position", 22) / 100.0
            y = geo.y() + int(geo.height() * pos_pct)
            self.move(x, y)

        self.show()
        self.raise_()

    def hide_preview(self):
        """미리보기 모드 종료."""
        self._preview_mode = False
        self._input.setPlaceholderText("무엇이든 말씀하세요...")
        self._input.setEnabled(True)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 16, 16)

        painter.fillPath(path, QBrush(QColor(0, 0, 0, 1)))  # 거의 투명한 배경
        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._is_recording:
                self.recording_cancel_requested.emit()
            else:
                self._dismiss()
        else:
            super().keyPressEvent(event)

    # ══════════════════════════════════════════
    # 이벤트 필터 (QApplication 레벨)
    #   - QLineEdit 키 이벤트: 즐겨찾기 탐색 + Escape
    #   - 마우스 클릭: 바깥 클릭 감지
    #   - 윈도우 비활성화: 다른 앱 클릭 감지
    # ══════════════════════════════════════════

    def _install_app_filter(self):
        if not self._app_filter_installed:
            app = QApplication.instance()
            if app:
                app.installEventFilter(self)
                self._app_filter_installed = True

    def _remove_app_filter(self):
        if self._app_filter_installed:
            app = QApplication.instance()
            if app:
                app.removeEventFilter(self)
            self._app_filter_installed = False

    def eventFilter(self, obj, event):
        etype = event.type()

        # ── QLineEdit 키보드 이벤트 ──
        if obj is self._input and etype == QEvent.Type.KeyPress:
            return self._handle_input_key(event)

        if not self.isVisible() or self._is_recording:
            return False

        # ── 바깥 클릭 감지 (Qt 위젯 내) ──
        if etype == QEvent.Type.MouseButtonPress and not self._preview_mode:
            if isinstance(obj, QWidget):
                if obj is not self and not self.isAncestorOf(obj):
                    self._dismiss()
                    return False

        # ── 다른 앱 클릭 → 윈도우 비활성화 ──
        if etype == QEvent.Type.WindowDeactivate and obj is self:
            QTimer.singleShot(100, self._check_deactivate)

        return False

    def _check_deactivate(self):
        """비활성화 후 실제로 닫아야 하는지 확인."""
        if self._preview_mode:
            return
        if not self.isVisible() or self.isActiveWindow():
            return
        active = QApplication.activeWindow()
        # 자식 다이얼로그/메뉴가 열려 있으면 무시
        if active is not None and active.parent() is self:
            return
        self._dismiss()

    def _handle_input_key(self, event) -> bool:
        """QLineEdit 키 이벤트 처리. True = 소비."""
        key = event.key()

        # Tab: 탭 전환 (fav ↔ clip)
        if key == Qt.Key.Key_Tab:
            if self._tab_bar.isVisible():
                new_tab = "clip" if self._current_tab == "fav" else "fav"
                self._switch_tab(new_tab)
            return True

        # Escape: 탐색 중이면 해제, 아니면 닫기
        if key == Qt.Key.Key_Escape:
            if self._fav_selected >= 0 or self._win_selected >= 0:
                self._fav_selected = -1
                self._win_selected = -1
                self._nav_zone = "fav"
                self._update_fav_highlight()
                self._update_clip_highlight()
                self._update_win_highlight()
            else:
                self._dismiss()
            return True

        # ── 즐겨찾기 탭: 열린 창 그리드 탐색 ──
        if self._current_tab == "fav" and self._nav_zone == "win" and self._win_selected >= 0:
            total = len(self._win_widgets)
            cols = self._WIN_GRID_COLS

            if key == Qt.Key.Key_Right:
                new = self._win_selected + 1
                if new < total:
                    self._win_selected = new
                    self._update_win_highlight()
                return True
            elif key == Qt.Key.Key_Left:
                new = self._win_selected - 1
                if new >= 0:
                    self._win_selected = new
                    self._update_win_highlight()
                return True
            elif key == Qt.Key.Key_Down:
                new = self._win_selected + cols
                if new < total:
                    self._win_selected = new
                    self._update_win_highlight()
                return True
            elif key == Qt.Key.Key_Up:
                new = self._win_selected - cols
                if new < 0:
                    # 열린 창 위로 → 즐겨찾기 마지막 항목으로
                    self._win_selected = -1
                    self._update_win_highlight()
                    if self._fav_widgets:
                        self._nav_zone = "fav"
                        self._fav_selected = len(self._fav_widgets) - 1
                        self._update_fav_highlight()
                    else:
                        self._nav_zone = "fav"
                else:
                    self._win_selected = new
                    self._update_win_highlight()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected_win()
                return True
            else:
                self._win_selected = -1
                self._nav_zone = "fav"
                self._update_win_highlight()
                return False

        # ── 클립보드 탭 탐색 모드 ──
        if self._current_tab == "clip" and self._fav_selected >= 0:
            total = len(self._clip_widgets)

            if key == Qt.Key.Key_Down:
                new = self._fav_selected + 1
                if new < total:
                    self._fav_selected = new
                    self._update_clip_highlight()
                return True
            elif key == Qt.Key.Key_Up:
                new = self._fav_selected - 1
                if new < 0:
                    self._fav_selected = -1
                else:
                    self._fav_selected = new
                self._update_clip_highlight()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected_clip()
                return True
            else:
                self._fav_selected = -1
                self._update_clip_highlight()
                return False

        # ── 즐겨찾기 탭 탐색 모드 ──
        if self._current_tab == "fav" and self._nav_zone == "fav" and self._fav_selected >= 0:
            total = len(self._fav_widgets)
            cols = self._FAV_GRID_COLS

            if key == Qt.Key.Key_Down:
                new = self._fav_selected + cols
                if new < total:
                    self._fav_selected = new
                    self._update_fav_highlight()
                elif self._win_widgets:
                    # 즐겨찾기 끝 → 열린 창 첫 항목으로
                    self._fav_selected = -1
                    self._update_fav_highlight()
                    self._nav_zone = "win"
                    self._win_selected = 0
                    self._update_win_highlight()
                return True
            elif key == Qt.Key.Key_Up:
                new = self._fav_selected - cols
                if new < 0:
                    self._fav_selected = -1
                else:
                    self._fav_selected = new
                self._update_fav_highlight()
                return True
            elif key == Qt.Key.Key_Right:
                new = self._fav_selected + 1
                if new < total:
                    self._fav_selected = new
                    self._update_fav_highlight()
                return True
            elif key == Qt.Key.Key_Left:
                new = self._fav_selected - 1
                if new < 0:
                    self._fav_selected = -1
                else:
                    self._fav_selected = new
                self._update_fav_highlight()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected_fav()
                return True
            else:
                # 타이핑 → 탐색 해제, 입력란 복귀
                self._fav_selected = -1
                self._update_fav_highlight()
                return False

        # ── 일반 입력 모드 ──
        if key == Qt.Key.Key_Down:
            if self._current_tab == "fav":
                if self._favorites_panel.isVisible() and self._fav_widgets:
                    self._nav_zone = "fav"
                    self._fav_selected = 0
                    self._update_fav_highlight()
                    return True
                if self._windows_panel.isVisible() and self._win_widgets:
                    self._nav_zone = "win"
                    self._win_selected = 0
                    self._update_win_highlight()
                    return True
            if self._current_tab == "clip" and self._clipboard_scroll.isVisible() and self._clip_widgets:
                self._fav_selected = 0
                self._update_clip_highlight()
                return True
            self.history_next_requested.emit()
            return True
        elif key == Qt.Key.Key_Up:
            self.history_prev_requested.emit(self._input.text())
            return True

        return False  # QLineEdit 기본 동작

    @staticmethod
    def _restore_korean_ime():
        """한글 입력기로 복원 (Alt 키 IME 전환 방지)"""
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        HKL_KOREAN = ctypes.windll.user32.LoadKeyboardLayoutW("00000412", 0)
        if HKL_KOREAN:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0050, 0, HKL_KOREAN)

    def toggle(self):
        if self._animating_out:
            return
        if self.isVisible():
            # 약간 지연 후 닫기 → Space 키가 다른 앱으로 누출되는 것 방지
            QTimer.singleShot(50, self._dismiss)
        else:
            self._show_centered()

    def _show_centered(self):
        """화면 상단 중앙에 표시"""
        self._auto_close_timer.stop()
        self._result.hide()
        self._recording_label.hide()
        self._input.clear()
        self._input.setEnabled(True)
        self._input.show()
        self._fav_selected = -1
        self._win_selected = -1
        self._nav_zone = "fav"
        self._update_fav_highlight()
        self._update_clip_highlight()
        self._update_win_highlight()

        # 탭 바 + 패널 표시
        has_favs = self._favorites_grid.count() > 0
        has_clips = len(self._clip_data) > 0
        has_wins = len(self._win_data) > 0
        if has_favs or has_clips or has_wins:
            self._tab_bar.show()
            self._update_tab_styles()
            self._favorites_panel.hide()
            self._clipboard_scroll.hide()
            self._windows_panel.hide()
            if self._current_tab == "fav":
                self._favorites_panel.show() if has_favs else None
                self._windows_panel.show() if has_wins else None
            elif self._current_tab == "clip":
                self._clipboard_scroll.show() if has_clips else None
        else:
            self._tab_bar.hide()
            self._favorites_panel.hide()
            self._clipboard_scroll.hide()
            self._windows_panel.hide()
        self.adjustSize()

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            pos_pct = self._prefs.get("spotlight_position", 22) / 100.0
            y = geo.y() + int(geo.height() * pos_pct)

            self.setWindowOpacity(0.0)
            self.move(x, y)
            self.show()
            self.raise_()
            self.activateWindow()
            self._input.setFocus()
            self._install_app_filter()

            self._anim_group = QPropertyAnimation(self, b"windowOpacity")
            self._anim_group.setDuration(180)
            self._anim_group.setStartValue(0.0)
            self._anim_group.setEndValue(1.0)
            self._anim_group.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim_group.start()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self._input.setFocus()
            self._install_app_filter()

        QTimer.singleShot(50, self._restore_korean_ime)

    def _dismiss(self):
        if self._animating_out:
            return
        self._auto_close_timer.stop()
        self._blink_timer.stop()
        self._is_recording = False
        self._remove_app_filter()

        # 페이드아웃 애니메이션
        self._animating_out = True
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(120)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self._on_dismiss_done)
        fade_out.start()
        self._fade_out_anim = fade_out

    def _on_dismiss_done(self):
        self._animating_out = False
        self.hide()
        self.setWindowOpacity(1.0)

    def _on_submit(self):
        text = self._input.text().strip()
        if text:
            self.input_submitted.emit(text)

    def set_input_text(self, text: str):
        """외부에서 입력란 텍스트 설정 + 커서 끝으로."""
        self._input.setText(text)
        self._input.setCursorPosition(len(text))

    # ── 녹음 모드 메서드 ──

    def show_recording(self):
        """Spotlight 열고 녹음 UI 표시"""
        self._auto_close_timer.stop()
        self._result.hide()
        self._tab_bar.hide()
        self._favorites_panel.hide()
        self._clipboard_scroll.hide()
        self._windows_panel.hide()
        self._input.hide()
        self._is_recording = True
        self._blink_visible = True
        self._recording_label.setText("\U0001f534 녹음 중...")
        self._recording_label.show()
        self._level_bar.setValue(0)
        self._level_bar.show()
        self._blink_timer.start()
        self.adjustSize()

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            pos_pct = self._prefs.get("spotlight_position", 22) / 100.0
            y = geo.y() + int(geo.height() * pos_pct)

            self.setWindowOpacity(0.0)
            self.move(x, y)
            self.show()
            self.raise_()
            self.activateWindow()
            self._install_app_filter()

            self._anim_group = QPropertyAnimation(self, b"windowOpacity")
            self._anim_group.setDuration(180)
            self._anim_group.setStartValue(0.0)
            self._anim_group.setEndValue(1.0)
            self._anim_group.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim_group.start()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self._install_app_filter()

        QTimer.singleShot(50, self._restore_korean_ime)

    def update_level(self, level: float):
        """음량 레벨 업데이트 (0.0 ~ 1.0)"""
        self._level_bar.setValue(int(level * 100))

    def show_transcribing(self):
        """인식 중... 상태 표시"""
        self._blink_timer.stop()
        self._level_bar.hide()
        self._recording_label.setText("\U0001f9e0 인식 중...")
        opacity = self._prefs.get("spotlight_opacity", 230)
        panel_bg = f"rgba(30, 30, 30, {max(opacity - 10, 0)})"
        self._recording_label.setStyleSheet(
            f"""
            QLabel {{
                background: {panel_bg};
                color: #74b9ff;
                border: 1px solid rgba(100, 150, 255, 0.3);
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 16px;
            }}
            """
        )
        self._recording_label.show()
        self.adjustSize()

    def stop_recording_ui(self):
        """녹음 UI 해제, 원래 상태 복원"""
        self._blink_timer.stop()
        self._is_recording = False
        self._recording_label.hide()
        self._level_bar.hide()
        # 녹음 라벨 스타일 원복 (테마 기반)
        opacity = self._prefs.get("spotlight_opacity", 230)
        panel_bg = f"rgba(30, 30, 30, {max(opacity - 10, 0)})"
        self._recording_label.setStyleSheet(
            f"""
            QLabel {{
                background: {panel_bg};
                color: #ff6b6b;
                border: 1px solid rgba(255, 100, 100, 0.3);
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 16px;
            }}
            """
        )
        self._input.show()
        self._input.setEnabled(True)
        self.adjustSize()

    def _toggle_blink(self):
        """녹음 인디케이터 깜박임"""
        self._blink_visible = not self._blink_visible
        if self._blink_visible:
            self._recording_label.setText("\U0001f534 녹음 중...")
        else:
            self._recording_label.setText("   녹음 중...")

    # ── 즐겨찾기 패널 ──

    @property
    def _FAV_GRID_COLS(self) -> int:
        # 아이템 100px + spacing 8px + 여백 32px
        usable = self._prefs.get("spotlight_width", 600) - 32
        return max(2, usable // 108)

    def set_favorites(self, items: list[dict]):
        """즐겨찾기 그리드 갱신."""
        # 기존 위젯 정리
        while self._favorites_grid.count():
            child = self._favorites_grid.takeAt(0)
            w = child.widget()
            if w:
                w.setParent(None)

        self._fav_data = list(items)
        self._fav_widgets = []
        self._fav_selected = -1

        # 아이템 배치
        idx = 0
        for fav in items:
            w = self._build_fav_item(fav)
            self._fav_widgets.append(w)
            self._favorites_grid.addWidget(
                w, idx // self._FAV_GRID_COLS, idx % self._FAV_GRID_COLS
            )
            idx += 1

        # '+' 추가 버튼
        add_btn = self._build_add_button()
        self._fav_widgets.append(add_btn)
        self._favorites_grid.addWidget(
            add_btn, idx // self._FAV_GRID_COLS, idx % self._FAV_GRID_COLS
        )

        if self.isVisible() and not self._is_recording and not self._result.isVisible():
            self._favorites_panel.show()
            self.adjustSize()

    def _build_fav_item(self, fav: dict) -> QWidget:
        """개별 즐겨찾기 아이콘 위젯."""
        container = QWidget()
        container.setFixedSize(100, 78)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setStyleSheet(
            """
            QWidget { background: transparent; border-radius: 8px; }
            QWidget:hover { background: rgba(255, 255, 255, 0.08); }
            """
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 아이콘
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            "background: rgba(255,255,255,0.06); border-radius: 10px;"
        )

        icon_path = fav.get("icon")
        if icon_path and os.path.isfile(icon_path):
            pm = QPixmap(icon_path).scaled(
                QSize(32, 32),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pm)
        else:
            # 이모지 폴백
            from ui.settings_window import APP_DISPLAY, SITE_DISPLAY
            emoji = "🌐"
            if fav["type"] == "app":
                emoji = APP_DISPLAY.get(fav["name"], APP_DISPLAY.get(fav["name"].lower(), "▪️"))
            else:
                emoji = SITE_DISPLAY.get(fav["name"], SITE_DISPLAY.get(fav["name"].lower(), "🌐"))
            icon_label.setText(emoji)
            icon_label.setStyleSheet(
                icon_label.styleSheet() + " font-size: 22px;"
            )

        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 이름
        name_label = QLabel(fav["name"])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFixedWidth(90)
        name_label.setStyleSheet(
            "color: #ccc; font-size: 11px; background: transparent;"
        )
        fm = name_label.fontMetrics()
        elided = fm.elidedText(fav["name"], Qt.TextElideMode.ElideRight, 88)
        name_label.setText(elided)
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 클릭 이벤트
        container.mousePressEvent = lambda event, f=fav: self._on_fav_press(event, f)

        return container

    def _on_fav_press(self, event, fav: dict):
        if event.button() == Qt.MouseButton.LeftButton:
            self.favorite_clicked.emit(fav)
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            action = menu.addAction("삭제")
            if menu.exec(QCursor.pos()) == action:
                self.favorite_remove_requested.emit(fav["name"])

    def _build_add_button(self) -> QWidget:
        """'+' 추가 버튼."""
        container = QWidget()
        container.setFixedSize(100, 78)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setStyleSheet(
            """
            QWidget { background: transparent; border-radius: 8px; }
            QWidget:hover { background: rgba(255, 255, 255, 0.08); }
            """
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("+")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            "background: rgba(255,255,255,0.06); border-radius: 10px; "
            "color: #888; font-size: 24px;"
        )
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel("추가")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(
            "color: #888; font-size: 11px; background: transparent;"
        )
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)

        container.mousePressEvent = lambda event: (
            self.favorite_add_requested.emit()
            if event.button() == Qt.MouseButton.LeftButton else None
        )
        return container

    # ── 즐겨찾기 키보드 탐색 ──

    _FAV_STYLE_NORMAL = (
        "QWidget { background: transparent; border-radius: 8px; }"
        "QWidget:hover { background: rgba(255, 255, 255, 0.08); }"
    )

    def _update_fav_highlight(self):
        """선택된 즐겨찾기 항목 하이라이트 갱신."""
        for i, w in enumerate(self._fav_widgets):
            if i == self._fav_selected:
                w.setStyleSheet(self._FAV_STYLE_SELECTED)
            else:
                w.setStyleSheet(self._FAV_STYLE_NORMAL)

    def _activate_selected_fav(self):
        """키보드로 선택된 즐겨찾기 실행."""
        if self._fav_selected < 0:
            return
        if self._fav_selected < len(self._fav_data):
            self.favorite_clicked.emit(self._fav_data[self._fav_selected])
        else:
            # '+' 추가 버튼
            self.favorite_add_requested.emit()

    # ── 탭 전환 ──

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        self._favorites_panel.hide()
        self._clipboard_scroll.hide()
        self._windows_panel.hide()
        if tab == "fav":
            self._tab_fav.setStyleSheet(self._TAB_STYLE_ACTIVE)
            self._tab_clip.setStyleSheet(self._TAB_STYLE_INACTIVE)
            self._favorites_panel.show()
            if self._win_data:
                self._windows_panel.show()
        else:
            self._tab_fav.setStyleSheet(self._TAB_STYLE_INACTIVE)
            self._tab_clip.setStyleSheet(self._TAB_STYLE_ACTIVE)
            self._clipboard_scroll.show()
        self._fav_selected = -1
        self._win_selected = -1
        self._nav_zone = "fav"
        self._update_fav_highlight()
        self._update_clip_highlight()
        self._update_win_highlight()
        self.adjustSize()

    def _update_tab_styles(self):
        """현재 탭에 맞게 탭 버튼 스타일 갱신."""
        self._tab_fav.setStyleSheet(
            self._TAB_STYLE_ACTIVE if self._current_tab == "fav" else self._TAB_STYLE_INACTIVE
        )
        self._tab_clip.setStyleSheet(
            self._TAB_STYLE_ACTIVE if self._current_tab == "clip" else self._TAB_STYLE_INACTIVE
        )

    # ── 클립보드 패널 ──

    def set_clipboard_items(self, items: list[dict]):
        """클립보드 패널 갱신."""
        # 기존 위젯 정리
        while self._clipboard_layout.count():
            child = self._clipboard_layout.takeAt(0)
            w = child.widget()
            if w:
                w.setParent(None)

        self._clip_data = list(items)
        self._clip_widgets = []

        for item in items:
            w = self._build_clip_item(item)
            self._clip_widgets.append(w)
            self._clipboard_layout.addWidget(w)

        self._clipboard_layout.addStretch()

        if not items:
            empty = QLabel("클립보드 히스토리가 비어 있습니다")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color: #555; font-size: 12px; padding: 20px; background: transparent;"
            )
            self._clipboard_layout.insertWidget(0, empty)
            self._clipboard_scroll.setFixedHeight(60)
        else:
            # 아이템 높이(52) + 간격(4) = 56 per item + 상하 마진(16)
            needed = len(items) * 56 + 16
            self._clipboard_scroll.setFixedHeight(min(needed, 350))

    @staticmethod
    def _relative_time(timestamp: float) -> str:
        """타임스탬프 → 상대 시간 문자열."""
        import time
        diff = time.time() - timestamp
        if diff < 60:
            return "방금"
        elif diff < 3600:
            return f"{int(diff // 60)}분 전"
        elif diff < 86400:
            return f"{int(diff // 3600)}시간 전"
        else:
            return f"{int(diff // 86400)}일 전"

    def _build_clip_item(self, item: dict) -> QWidget:
        """개별 클립보드 항목 위젯."""
        container = QWidget()
        container.setFixedHeight(52)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setStyleSheet(
            "QWidget { background: transparent; border-radius: 8px; }"
            "QWidget:hover { background: rgba(255, 255, 255, 0.08); }"
        )

        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(8)

        # 타입 아이콘 또는 썸네일
        if item["type"] == "image":
            thumb_label = QLabel()
            thumb_label.setFixedSize(36, 36)
            thumb_label.setStyleSheet(
                "background: rgba(255,255,255,0.06); border-radius: 6px;"
            )
            # 이미지 썸네일 로드 시도
            data_path = item.get("data_path", "")
            if data_path and os.path.isfile(data_path):
                pm = QPixmap(data_path).scaled(
                    QSize(36, 36),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb_label.setPixmap(pm)
            else:
                thumb_label.setText("🖼️")
                thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb_label.setStyleSheet(
                    thumb_label.styleSheet() + " font-size: 18px;"
                )
            h_layout.addWidget(thumb_label)
        else:
            icon_label = QLabel("📝")
            icon_label.setFixedSize(36, 36)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet(
                "background: rgba(255,255,255,0.06); border-radius: 6px; font-size: 18px;"
            )
            h_layout.addWidget(icon_label)

        # 중앙: preview + 시간
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        preview_text = item.get("preview", "")
        # 한 줄로 표시
        preview_text = preview_text.replace("\n", " ").replace("\r", "")
        if len(preview_text) > 60:
            preview_text = preview_text[:60] + "…"

        preview_label = QLabel(preview_text)
        preview_label.setStyleSheet(
            "color: #ddd; font-size: 12px; background: transparent;"
        )
        fm = preview_label.fontMetrics()
        elided = fm.elidedText(preview_text, Qt.TextElideMode.ElideRight, 420)
        preview_label.setText(elided)
        text_layout.addWidget(preview_label)

        time_str = self._relative_time(item.get("timestamp", 0))
        size_bytes = item.get("size_bytes", 0)
        if size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} B"
        meta_label = QLabel(f"{time_str} · {size_str}")
        meta_label.setStyleSheet(
            "color: #666; font-size: 10px; background: transparent;"
        )
        text_layout.addWidget(meta_label)

        h_layout.addLayout(text_layout, 1)

        # 클릭 → 재복사
        container.mousePressEvent = lambda event, it=item: self._on_clip_press(event, it)

        return container

    def _on_clip_press(self, event, item: dict):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clipboard_item_clicked.emit(item["id"])
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            action = menu.addAction("삭제")
            if menu.exec(QCursor.pos()) == action:
                self.clipboard_item_remove_requested.emit(item["id"])

    # ── 클립보드 키보드 탐색 ──

    _CLIP_STYLE_NORMAL = (
        "QWidget { background: transparent; border-radius: 8px; }"
        "QWidget:hover { background: rgba(255, 255, 255, 0.08); }"
    )

    def _update_clip_highlight(self):
        """선택된 클립보드 항목 하이라이트 갱신."""
        for i, w in enumerate(self._clip_widgets):
            if self._current_tab == "clip" and i == self._fav_selected:
                w.setStyleSheet(self._CLIP_STYLE_SELECTED)
            else:
                w.setStyleSheet(self._CLIP_STYLE_NORMAL)

    def _activate_selected_clip(self):
        """키보드로 선택된 클립보드 항목 실행."""
        if self._fav_selected < 0 or self._fav_selected >= len(self._clip_data):
            return
        self.clipboard_item_clicked.emit(self._clip_data[self._fav_selected]["id"])

    # ── 열린 창 패널 ──

    # 프로세스 → 이모지 매핑
    _PROCESS_EMOJI = {
        "explorer.exe": "📁", "chrome.exe": "🌐", "msedge.exe": "🌐",
        "firefox.exe": "🦊", "brave.exe": "🦁", "whale.exe": "🐋",
        "code.exe": "💻", "notepad.exe": "📝", "notepad++.exe": "📝",
        "discord.exe": "💬", "slack.exe": "💬", "telegram.exe": "💬",
        "kakaotalk.exe": "💬", "spotify.exe": "🎵", "vlc.exe": "🎬",
        "winword.exe": "📄", "excel.exe": "📊", "powerpnt.exe": "📊",
        "cmd.exe": "⬛", "powershell.exe": "⬛", "windowsterminal.exe": "⬛",
    }

    _THUMB_W = 130
    _THUMB_H = 80

    @property
    def _WIN_GRID_COLS(self) -> int:
        # 카드 138px(130+8) + 여백 20px
        usable = self._prefs.get("spotlight_width", 600) - 20
        return max(2, usable // 144)

    @staticmethod
    def _capture_thumbnail(hwnd: int, max_w: int, max_h: int) -> QPixmap:
        """PrintWindow API로 창 썸네일 캡처."""
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return QPixmap()

            hwnd_dc = user32.GetWindowDC(hwnd)
            if not hwnd_dc:
                return QPixmap()
            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
            old = gdi32.SelectObject(mem_dc, bitmap)

            PW_RENDERFULLCONTENT = 2
            user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32

            buf = (ctypes.c_char * (w * h * 4))()
            gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.SelectObject(mem_dc, old)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

            img = QImage(buf, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
            if img.isNull():
                return QPixmap()
            return QPixmap.fromImage(img).scaled(
                QSize(max_w, max_h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            return QPixmap()

    def set_windows_items(self, items: list[dict]):
        """열린 창 그리드 갱신 (썸네일은 비동기 로드)."""
        # 기존 위젯/레이아웃 정리
        while self._windows_grid_layout.count():
            child = self._windows_grid_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
            if child.layout():
                sub = child.layout()
                while sub.count():
                    sc = sub.takeAt(0)
                    if sc.widget():
                        sc.widget().setParent(None)

        self._win_data = list(items)
        self._win_widgets = []
        self._win_selected = -1
        self._thumb_labels: list[QLabel] = []
        self._thumb_queue: list[int] = []

        if not items:
            self._windows_panel.hide()
            return

        # 섹션 헤더
        header = QLabel("열린 창")
        header.setStyleSheet(
            "color: #888; font-size: 11px; padding: 0 2px; background: transparent;"
        )
        self._windows_grid_layout.addWidget(header)

        # 그리드 배치 (placeholder)
        cols = self._WIN_GRID_COLS
        row_layout = None
        for i, item in enumerate(items):
            if i % cols == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(6)
                self._windows_grid_layout.addLayout(row_layout)
            w, thumb = self._build_win_item(item)
            self._win_widgets.append(w)
            self._thumb_labels.append(thumb)
            row_layout.addWidget(w)

        # 마지막 줄 남는 칸
        if row_layout and len(items) % cols != 0:
            for _ in range(cols - len(items) % cols):
                spacer = QWidget()
                spacer.setFixedSize(self._THUMB_W + 8, 1)
                spacer.setStyleSheet("background: transparent;")
                row_layout.addWidget(spacer)

        # 썸네일 비동기 로드 시작
        self._thumb_queue = list(range(len(items)))
        QTimer.singleShot(0, self._load_next_thumbnail)

    def _load_next_thumbnail(self):
        """썸네일을 하나씩 비동기 로드."""
        if not self._thumb_queue or not self.isVisible():
            return
        idx = self._thumb_queue.pop(0)
        if idx < len(self._win_data) and idx < len(self._thumb_labels):
            hwnd = self._win_data[idx]["hwnd"]
            pm = self._capture_thumbnail(hwnd, self._THUMB_W, self._THUMB_H)
            if pm and not pm.isNull():
                self._thumb_labels[idx].setPixmap(pm)
        # 다음 썸네일
        if self._thumb_queue:
            QTimer.singleShot(0, self._load_next_thumbnail)

    def _build_win_item(self, item: dict) -> tuple[QWidget, QLabel]:
        """개별 열린 창 카드 (placeholder + 제목). (container, thumb_label) 반환."""
        card_w = self._THUMB_W + 8
        card_h = self._THUMB_H + 28
        container = QWidget()
        container.setFixedSize(card_w, card_h)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setStyleSheet(
            "QWidget { background: transparent; border-radius: 6px; }"
            "QWidget:hover { background: rgba(255, 255, 255, 0.08); }"
        )

        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(4, 3, 4, 2)
        v_layout.setSpacing(2)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 썸네일 placeholder
        thumb_label = QLabel()
        thumb_label.setFixedSize(self._THUMB_W, self._THUMB_H)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        proc = item.get("process_name", "").lower()
        emoji = self._PROCESS_EMOJI.get(proc, "▪")
        thumb_label.setText(emoji)
        thumb_label.setStyleSheet(
            "background: rgba(255,255,255,0.04); "
            "border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; "
            "font-size: 24px; color: #666;"
        )
        v_layout.addWidget(thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 제목 (1줄)
        title = item.get("title", "")
        title_label = QLabel()
        title_label.setFixedWidth(self._THUMB_W)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            "color: #bbb; font-size: 10px; background: transparent;"
        )
        fm = title_label.fontMetrics()
        elided = fm.elidedText(title, Qt.TextElideMode.ElideRight, self._THUMB_W - 4)
        title_label.setText(elided)
        v_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        container.mousePressEvent = lambda event, it=item: self._on_win_press(event, it)
        return container, thumb_label

    def _on_win_press(self, event, item: dict):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window_clicked.emit(item["hwnd"])

    _WIN_STYLE_NORMAL = (
        "QWidget { background: transparent; border-radius: 8px; }"
        "QWidget:hover { background: rgba(255, 255, 255, 0.08); }"
    )

    def _update_win_highlight(self):
        """선택된 열린 창 항목 하이라이트 갱신."""
        for i, w in enumerate(self._win_widgets):
            if self._nav_zone == "win" and i == self._win_selected:
                w.setStyleSheet(self._WIN_STYLE_SELECTED)
            else:
                w.setStyleSheet(self._WIN_STYLE_NORMAL)

    def _activate_selected_win(self):
        """키보드로 선택된 열린 창 항목 실행."""
        if self._win_selected < 0 or self._win_selected >= len(self._win_data):
            return
        self.window_clicked.emit(self._win_data[self._win_selected]["hwnd"])

    # ── 기존 결과 표시 메서드 ──

    def show_loading(self):
        self._input.setEnabled(False)
        self._tab_bar.hide()
        self._favorites_panel.hide()
        self._clipboard_scroll.hide()
        self._windows_panel.hide()
        self._result.setText("\U0001f9e0 처리 중...")
        self._result.show()
        self.adjustSize()

    def show_result(self, text):
        self._result.setText(text)
        self._result.show()
        self.adjustSize()
        ms = self._prefs.get("result_auto_close_ms", RESULT_AUTO_CLOSE_MS)
        self._auto_close_timer.start(ms)

    def show_error(self, text):
        self._result.setText(f"\u274c {text}")
        self._result.show()
        self.adjustSize()
        ms = self._prefs.get("result_auto_close_ms", RESULT_AUTO_CLOSE_MS)
        self._auto_close_timer.start(ms)
