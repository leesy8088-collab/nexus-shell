"""
SettingsWindow: 키워드 단축키 설정 다이얼로그 (미니멀리즘 디자인)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QGroupBox, QMessageBox,
    QTabWidget, QWidget, QGridLayout, QScrollArea, QSizePolicy, QMenu,
    QGraphicsDropShadowEffect, QFrame, QFileDialog, QSlider,
    QKeySequenceEdit, QStackedWidget, QCheckBox,
)
from PySide6.QtCore import Signal, Qt, QRect, QThread
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QBrush, QCursor, QKeySequence

from config import APP_ALIASES, SITE_ALIASES, DEFAULT_PREFS, load_preferences, save_preferences
from utils.app_scanner import (
    scan_installed_apps, add_user_app, remove_user_app,
    load_user_apps_raw, get_discovered_apps,
)
from utils.favorites import FavoritesManager


# ── 시스템 다크/라이트 모드 감지 ──

def _is_dark_mode() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        return True

_DARK = _is_dark_mode()


# ── 미니멀 팔레트 (저채도, 고대비, Border-less) ──

class _Palette:
    if _DARK:
        BG           = "#0f0f0f"
        BG_CARD      = "#1a1a1a"
        BG_HOVER     = "#252525"
        BG_SELECTED  = "rgba(99, 102, 241, 0.15)"
        BORDER       = "rgba(255, 255, 255, 0.08)"
        TEXT         = "#a0a0a0"
        TEXT_BRIGHT  = "#ffffff"
        TEXT_DIM     = "#555555"
        ACCENT       = "#6366f1"
        ACCENT_HOVER = "#818cf8"
        ACCENT_DIM   = "rgba(99, 102, 241, 0.1)"
        ACCENT_TEXT  = "#ffffff"
        DANGER       = "#ff4646"
        DANGER_DIM   = "rgba(255, 70, 70, 0.1)"
        SUCCESS      = "#34d399"
        SUCCESS_HOVER = "#2cc48a"
        MON_BG       = "#111111"
        MON_EMPTY    = "#141414"
        MON_EMPTY_HOVER = "#1c1c1c"
        MON_FILL     = "#6366f1"
        MON_FILL_HOVER = "#818cf8"
        MON_TEXT_DIM = "#444444"
        SCROLLBAR    = "#252525"
    else:
        BG           = "#ffffff"
        BG_CARD      = "#f5f5f7"
        BG_HOVER     = "#e8e8ed"
        BG_SELECTED  = "rgba(0, 113, 227, 0.1)"
        BORDER       = "rgba(0, 0, 0, 0.08)"
        TEXT         = "#6e6e73"
        TEXT_BRIGHT  = "#1d1d1f"
        TEXT_DIM     = "#aeaeb2"
        ACCENT       = "#0071e3"
        ACCENT_HOVER = "#0077ED"
        ACCENT_DIM   = "rgba(0, 113, 227, 0.08)"
        ACCENT_TEXT  = "#ffffff"
        DANGER       = "#ff3b30"
        DANGER_DIM   = "rgba(255, 59, 48, 0.08)"
        SUCCESS      = "#34c759"
        SUCCESS_HOVER = "#2db84e"
        MON_BG       = "#f0f0f2"
        MON_EMPTY    = "#e5e5e7"
        MON_EMPTY_HOVER = "#dcdce0"
        MON_FILL     = "#0071e3"
        MON_FILL_HOVER = "#0077ED"
        MON_TEXT_DIM = "#c0c0c4"
        SCROLLBAR    = "#e0e0e0"

P = _Palette


# ── 앱 아이콘 매핑 ──
APP_DISPLAY = {
    "크롬":     "🌐",
    "엣지":     "🌐",
    "메모장":    "📝",
    "계산기":    "🧮",
    "탐색기":    "📁",
    "vscode":   "💻",
    "비주얼스튜디오코드": "💻",
    "그림판":    "🎨",
    "cmd":      "⬛",
    "터미널":    "⬛",
    "powershell": "⬛",
    "설정":     "⚙️",
    "작업관리자": "📊",
}

# ── 사이트 아이콘 매핑 ──
SITE_DISPLAY = {
    "유튜브":    "📺",
    "네이버":    "🟢",
    "구글":     "🔍",
    "깃허브":    "🐙",
    "챗지피티":   "🤖",
}

# ── 시스템 정보 옵션 ──
SYSTEM_OPTIONS = [
    ("cpu",     "🖥️", "CPU"),
    ("memory",  "💾", "메모리"),
    ("disk",    "💿", "디스크"),
    ("battery", "🔋", "배터리"),
    ("network", "🌐", "네트워크"),
    ("all",     "📊", "전체 정보"),
]

# ── 화면 배치 옵션 (표시용) ──
SNAP_OPTIONS = [
    ("left",     "◀️", "왼쪽 분할"),
    ("right",    "▶️", "오른쪽 분할"),
    ("maximize", "⬜",  "최대화"),
    ("minimize", "➖",  "최소화"),
]

GRID_COLS = 3


def _unique_items(aliases: dict, icons: dict):
    """중복 제거. 같은 대상이면 한글 이름 우선."""
    value_map: dict[str, str] = {}
    for name, value in aliases.items():
        if value not in value_map:
            value_map[value] = name
        else:
            existing = value_map[value]
            if existing.isascii() and not name.isascii():
                value_map[value] = name
    result = []
    for _value, name in value_map.items():
        icon = icons.get(name, "▪️")
        result.append((name, icon))
    return result


# ══════════════════════════════════════════
# 미니멀 QSS 스타일
# ══════════════════════════════════════════

def _build_minimal_qss() -> str:
    return f"""
    /* ── 다이얼로그 ── */
    QDialog {{
        background: {P.BG};
        color: {P.TEXT};
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 13px;
    }}

    /* ── 라벨 ── */
    QLabel {{
        color: {P.TEXT};
        font-size: 13px;
        background: transparent;
    }}

    /* ── 에디터 캔버스 (우측 카드) ── */
    QFrame#EditorCanvas {{
        background: {P.BG_CARD};
        border: 1px solid {P.BORDER};
        border-radius: 16px;
    }}

    /* ── 입력 필드: 은은한 테두리 + 포커스 강조 ── */
    QLineEdit {{
        background: {P.BG_CARD};
        color: {P.TEXT_BRIGHT};
        border: 1px solid {P.BORDER};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 14px;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QLineEdit:focus {{
        border: 1px solid {P.ACCENT};
    }}
    QLineEdit:placeholder {{
        color: {P.TEXT_DIM};
    }}

    /* ── 키워드 제목 입력 (투명 배경, 큰 폰트) ── */
    QLineEdit#keyword_title {{
        background: transparent;
        border: none;
        border-radius: 0px;
        padding: 0px;
        font-size: 20px;
        font-weight: 600;
        color: {P.TEXT_BRIGHT};
    }}
    QLineEdit#keyword_title:focus {{
        border: none;
    }}

    /* ── 사이드바 리스트 ── */
    QListWidget#sidebar {{
        background: transparent;
        border: none;
        outline: none;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QListWidget#sidebar::item {{
        background: transparent;
        color: {P.TEXT};
        border-radius: 8px;
        margin-bottom: 2px;
        padding: 10px 12px;
    }}
    QListWidget#sidebar::item:selected {{
        background: {P.BG_CARD};
        color: {P.TEXT_BRIGHT};
        font-weight: 600;
    }}
    QListWidget#sidebar::item:hover:!selected {{
        background: {P.BG_HOVER};
    }}

    /* ── 일반 리스트: 떠 있는 카드 느낌 ── */
    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QListWidget::item {{
        background: {P.BG_CARD};
        color: {P.TEXT};
        border-radius: 10px;
        margin-bottom: 4px;
        padding: 8px 12px;
    }}
    QListWidget::item:selected {{
        background: {P.ACCENT_DIM};
        color: {P.ACCENT};
        font-weight: bold;
    }}
    QListWidget::item:hover:!selected {{
        background: {P.BG_HOVER};
    }}

    /* ── 탭: 선 없이 텍스트 강조 ── */
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {P.TEXT};
        padding: 10px 18px;
        margin-right: 4px;
        font-weight: 500;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 12px;
        border: none;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {P.ACCENT};
        border-bottom: 2px solid {P.ACCENT};
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        color: {P.TEXT_BRIGHT};
    }}

    /* ── 버튼: Flat + 은은한 테두리 ── */
    QPushButton {{
        background: {P.BG_HOVER};
        color: {P.TEXT_BRIGHT};
        border: 1px solid {P.BORDER};
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QPushButton:hover {{
        background: {P.BG_HOVER};
    }}
    QPushButton:pressed {{
        background: {P.BG_CARD};
    }}

    /* ── 저장 버튼 ── */
    QPushButton#save_btn {{
        background: {P.ACCENT};
        color: {P.ACCENT_TEXT};
        border: none;
        border-radius: 10px;
        padding: 14px;
        font-size: 14px;
        font-weight: bold;
    }}
    QPushButton#save_btn:hover {{
        background: {P.ACCENT_HOVER};
    }}

    /* ── 삭제 버튼 ── */
    QPushButton#delete_btn {{
        background: transparent;
        color: {P.DANGER};
        border: 1px solid {P.DANGER};
        font-weight: 500;
    }}
    QPushButton#delete_btn:hover {{
        background: {P.DANGER_DIM};
    }}

    /* ── 적용(초록) 버튼 ── */
    QPushButton#apply_btn {{
        background: {P.SUCCESS};
        color: {P.ACCENT_TEXT};
        border: none;
        border-radius: 8px;
        padding: 10px;
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton#apply_btn:hover {{
        background: {P.SUCCESS_HOVER};
    }}

    /* ── 피커 버튼 ── */
    QPushButton#picker_btn {{
        background: {P.BG_CARD};
        border: 1px solid {P.BORDER};
        border-radius: 10px;
        padding: 8px 6px;
        font-size: 13px;
        min-width: 90px;
        min-height: 48px;
    }}
    QPushButton#picker_btn:hover {{
        background: {P.BG_HOVER};
        border: 1px solid {P.ACCENT};
    }}

    /* ── 그룹 박스: 투명 배경, 은은한 테두리 ── */
    QGroupBox {{
        background: transparent;
        border: 1px solid {P.BORDER};
        border-radius: 12px;
        margin-top: 12px;
        padding: 14px 10px 8px 10px;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px;
        padding: 0 6px;
        color: {P.TEXT};
        font-size: 11px;
        font-weight: bold;
    }}

    /* ── 명령 시퀀스 리스트 (에디터 내부) ── */
    QListWidget#cmd_sequence {{
        background: {P.BG};
        border-radius: 12px;
        border: 1px solid {P.BORDER};
        padding: 8px;
    }}

    /* ── 스크롤 영역 ── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    /* ── 스크롤바: 극도로 얇게 ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 4px;
        border-radius: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {P.SCROLLBAR};
        border-radius: 2px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 4px;
        border-radius: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {P.SCROLLBAR};
        border-radius: 2px;
        min-width: 30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ── 메뉴 ── */
    QMenu {{
        background: {P.BG_CARD};
        color: {P.TEXT};
        border: 1px solid {P.BORDER};
        border-radius: 12px;
        padding: 6px;
        font-size: 13px;
        font-family: "Pretendard", "Inter", "Segoe UI", "Malgun Gothic", sans-serif;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 8px;
    }}
    QMenu::item:selected {{
        background: {P.BG_HOVER};
        color: {P.TEXT_BRIGHT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {P.BORDER};
        margin: 4px 12px;
    }}
"""


# ══════════════════════════════════════════
# 모니터 레이아웃 위젯 (추상 카드 형태)
# ══════════════════════════════════════════

class MonitorLayoutWidget(QWidget):
    """추상적인 카드 형태의 레이아웃 에디터."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout_type = "split"
        self._zones: dict[str, dict | None] = {}
        self._hover_zone: str | None = None
        self._reset_zones()
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── 외부 API ──

    def set_layout_type(self, layout_type: str):
        self._layout_type = layout_type
        self._reset_zones()
        self.update()

    def get_commands(self) -> list[dict]:
        """현재 배치 -> launch_and_snap 명령 시퀀스 생성."""
        commands = []
        zone_list = [("full", "maximize")] if self._layout_type == "single" \
            else [("left", "left"), ("right", "right")]

        for zone_key, snap_pos in zone_list:
            data = self._zones.get(zone_key)
            if not data:
                continue
            orig = data["cmd"]
            args = {"position": snap_pos}
            args.update(orig["arguments"])
            commands.append({"function": "launch_and_snap", "arguments": args})
        return commands

    def has_assignments(self) -> bool:
        return any(v is not None for v in self._zones.values())

    def reset(self):
        self._reset_zones()
        self.update()

    # ── 내부 ──

    def _reset_zones(self):
        if self._layout_type == "single":
            self._zones = {"full": None}
        else:
            self._zones = {"left": None, "right": None}

    def _zone_rects(self) -> dict[str, QRect]:
        margin = 16
        w = self.width() - margin * 2
        h = int(w / 1.78)
        if h > self.height() - margin * 2:
            h = self.height() - margin * 2
            w = int(h * 1.78)
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2

        if self._layout_type == "single":
            return {"full": QRect(x, y, w, h)}
        gap = 10
        half = (w - gap) // 2
        return {
            "left":  QRect(x, y, half, h),
            "right": QRect(x + half + gap, y, w - half - gap, h),
        }

    # ── 페인트 ──

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        for key, rect in self._zone_rects().items():
            data = self._zones.get(key)
            is_hover = (key == self._hover_zone)

            if data:
                fill = QColor(P.MON_FILL_HOVER) if is_hover else QColor(P.MON_FILL)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(fill))
                p.drawRoundedRect(rect, 16, 16)
                p.setPen(QColor("white"))
                p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                           f"{data['icon']}\n{data['name']}")
            else:
                bg = QColor(P.MON_EMPTY_HOVER) if is_hover else QColor(P.MON_EMPTY)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(bg))
                p.drawRoundedRect(rect, 16, 16)
                p.setPen(QColor(P.MON_TEXT_DIM))
                p.setFont(QFont("Segoe UI", 18, QFont.Weight.ExtraLight))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "+")

        p.end()

    # ── 마우스 ──

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        old = self._hover_zone
        self._hover_zone = None
        for key, rect in self._zone_rects().items():
            if rect.contains(pos):
                self._hover_zone = key
                break
        if old != self._hover_zone:
            self.update()

    def leaveEvent(self, event):
        self._hover_zone = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        for key, rect in self._zone_rects().items():
            if rect.contains(pos):
                self._show_picker(key)
                return

    def _show_picker(self, zone_key: str):
        menu = QMenu(self)

        menu.addSection("앱")
        for name, icon in _unique_items(APP_ALIASES, APP_DISPLAY):
            action = menu.addAction(f"{icon}  {name}")
            action.setData({"name": name, "icon": icon,
                            "cmd": {"function": "run_app",
                                    "arguments": {"app_name": name}}})

        menu.addSection("사이트")
        for name, icon in _unique_items(SITE_ALIASES, SITE_DISPLAY):
            action = menu.addAction(f"{icon}  {name}")
            action.setData({"name": name, "icon": icon,
                            "cmd": {"function": "open_url",
                                    "arguments": {"site_name": name}}})

        if self._zones.get(zone_key):
            menu.addSeparator()
            clear_action = menu.addAction("✕  비우기")
            clear_action.setData(None)

        chosen = menu.exec(QCursor.pos())
        if chosen:
            self._zones[zone_key] = chosen.data()
            self.update()


# ══════════════════════════════════════════
# 앱 스캔 워커 (백그라운드)
# ══════════════════════════════════════════

class _ScanWorker(QThread):
    """백그라운드에서 설치 앱 후보를 스캔."""
    finished = Signal(dict)  # {display_name: exe_path}

    def run(self):
        try:
            apps = get_discovered_apps()
        except Exception:
            apps = {}
        self.finished.emit(apps)


# ══════════════════════════════════════════
# 앱 선택 다이얼로그
# ══════════════════════════════════════════

class AppPickerDialog(QDialog):
    """발견된 앱 목록에서 원하는 앱을 골라 등록."""

    apps_selected = Signal(dict)  # {name: path, ...}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설치된 앱 추가")
        self.setMinimumSize(420, 500)
        self.setStyleSheet(_build_minimal_qss())

        self._all_apps: dict[str, str] = {}
        self._setup_ui()
        self._start_scan()

    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(10)

        # 검색 입력
        self._search = QLineEdit()
        self._search.setPlaceholderText("앱 검색...")
        self._search.textChanged.connect(self._filter_list)
        lo.addWidget(self._search)

        # 앱 목록 (체크박스)
        self._list = QListWidget()
        lo.addWidget(self._list, 1)

        # 상태 라벨
        self._status = QLabel("스캔 중...")
        self._status.setStyleSheet(f"color: {P.TEXT_DIM}; font-size: 12px;")
        lo.addWidget(self._status)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_browse = QPushButton("📂 직접 선택")
        btn_browse.setToolTip("exe 파일을 직접 찾아서 추가")
        btn_browse.clicked.connect(self._on_browse)
        btn_row.addWidget(btn_browse)

        btn_row.addStretch()

        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_add = QPushButton("추가")
        btn_add.setObjectName("apply_btn")
        btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(btn_add)

        lo.addLayout(btn_row)

    def _start_scan(self):
        self._worker = _ScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, apps: dict[str, str]):
        self._all_apps = apps
        self._populate_list(apps)
        count = len(apps)
        self._status.setText(f"{count}개 앱 발견" if count else "발견된 앱이 없습니다")

    def _populate_list(self, apps: dict[str, str]):
        self._list.clear()
        for name, path in sorted(apps.items(), key=lambda x: x[0].lower()):
            item = QListWidgetItem(f"{name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, (name, path))
            self._list.addItem(item)

    def _filter_list(self, text: str):
        query = text.strip().lower()
        if not query:
            filtered = self._all_apps
        else:
            filtered = {
                n: p for n, p in self._all_apps.items()
                if query in n.lower()
            }
        self._populate_list(filtered)

    def _on_browse(self):
        """파일 탐색기로 exe 직접 선택."""
        import os
        path, _ = QFileDialog.getOpenFileName(
            self, "실행 파일 선택", "",
            "실행 파일 (*.exe);;모든 파일 (*)",
        )
        if not path:
            return
        # 파일명에서 표시 이름 추출
        default_name = os.path.splitext(os.path.basename(path))[0]
        # 이름 입력 다이얼로그
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "앱 이름", "등록할 이름:", text=default_name,
        )
        if not ok or not name.strip():
            return
        self.apps_selected.emit({name.strip(): path})
        self.accept()

    def _on_add(self):
        selected: dict[str, str] = {}
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                name, path = item.data(Qt.ItemDataRole.UserRole)
                selected[name] = path
        if not selected:
            QMessageBox.warning(self, "알림", "추가할 앱을 선택하세요.")
            return
        self.apps_selected.emit(selected)
        self.accept()


# ══════════════════════════════════════════
# 설정 윈도우
# ══════════════════════════════════════════

class SettingsWindow(QDialog):
    shortcuts_updated = Signal()
    preferences_changed = Signal(dict)
    preview_requested = Signal(bool)  # True=미리보기 켜기, False=끄기

    def __init__(self, shortcut_manager, favorites_manager=None,
                 preferences: dict | None = None, parent=None):
        super().__init__(parent)
        self._manager = shortcut_manager
        self._current_keyword = None
        self._user_app_names: set[str] = set()
        self._favorites = favorites_manager or FavoritesManager()
        self._prefs = dict(preferences or load_preferences())

        self.setWindowTitle("Nexus Shell Settings")
        self.setMinimumSize(950, 760)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet(_build_minimal_qss())
        self._setup_ui()
        self._refresh_keyword_list()

    def set_preferences(self, prefs: dict):
        """외부에서 preferences 갱신 (설정 창 재오픈 시)."""
        self._prefs = dict(prefs)
        self._load_prefs_to_ui()

    def closeEvent(self, event):
        """설정 창 닫힐 때 미리보기 종료."""
        self.preview_requested.emit(False)
        super().closeEvent(event)

    # ══════════════════════════════════════════
    # UI 구성
    # ══════════════════════════════════════════

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(32)

        # ── 좌측: 사이드바 ──
        left = QVBoxLayout()
        left.setSpacing(12)

        brand = QLabel("NEXUS SHELL")
        brand.setStyleSheet(
            f"font-weight: 900; letter-spacing: 3px; font-size: 14px; "
            f"color: {P.TEXT_BRIGHT}; margin-bottom: 16px;"
        )
        left.addWidget(brand)

        # 일반 설정 버튼
        self._btn_general = QPushButton("⚙  일반 설정")
        self._btn_general.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_general.clicked.connect(self._show_general_page)
        left.addWidget(self._btn_general)

        lbl = QLabel("SHORTCUTS")
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 800; "
            f"letter-spacing: 2px; color: {P.ACCENT}; margin-top: 8px;"
        )
        left.addWidget(lbl)

        self._keyword_list = QListWidget()
        self._keyword_list.setObjectName("sidebar")
        self._keyword_list.currentItemChanged.connect(self._on_keyword_selected)
        left.addWidget(self._keyword_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_add_kw = QPushButton("+ 새 단축키")
        self._btn_add_kw.clicked.connect(self._add_keyword)
        self._btn_del_kw = QPushButton("삭제")
        self._btn_del_kw.setObjectName("delete_btn")
        self._btn_del_kw.clicked.connect(self._delete_keyword)
        btn_row.addWidget(self._btn_add_kw)
        btn_row.addWidget(self._btn_del_kw)
        left.addLayout(btn_row)

        root.addLayout(left, 1)

        # ── 우측: 스택 (일반 설정 / 단축키 에디터) ──
        self._right_stack = QStackedWidget()

        # 페이지 0: 일반 설정
        self._general_page = self._build_general_page()
        self._right_stack.addWidget(self._general_page)

        # 페이지 1: 단축키 에디터
        self._editor_page = self._build_editor_page()
        self._right_stack.addWidget(self._editor_page)

        self._right_stack.setCurrentIndex(1)  # 기본: 단축키 에디터
        root.addWidget(self._right_stack, 3)

        self._update_sidebar_style()

    def _build_general_page(self) -> QFrame:
        """일반 설정 전체 페이지 (우측 패널)."""
        canvas = QFrame()
        canvas.setObjectName("EditorCanvas")
        lo = QVBoxLayout(canvas)
        lo.setContentsMargins(28, 28, 28, 28)
        lo.setSpacing(20)

        # 헤더
        title = QLabel("일반 설정")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: {P.TEXT_BRIGHT};"
        )
        lo.addWidget(title)

        # ── 핫키 섹션 ──
        hotkey_group = QGroupBox("단축키")
        hg_lo = QVBoxLayout(hotkey_group)
        hg_lo.setSpacing(12)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Spotlight 단축키"))
        self._hotkey_spotlight_edit = QKeySequenceEdit()
        self._hotkey_spotlight_edit.setFixedWidth(200)
        row1.addStretch()
        row1.addWidget(self._hotkey_spotlight_edit)
        hg_lo.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("음성 단축키"))
        self._hotkey_voice_edit = QKeySequenceEdit()
        self._hotkey_voice_edit.setFixedWidth(200)
        row2.addStretch()
        row2.addWidget(self._hotkey_voice_edit)
        hg_lo.addLayout(row2)

        lo.addWidget(hotkey_group)

        # ── Spotlight UI 섹션 ──
        ui_group = QGroupBox("Spotlight UI")
        ug_lo = QVBoxLayout(ui_group)
        ug_lo.setSpacing(12)

        # 너비
        row_w = QHBoxLayout()
        row_w.addWidget(QLabel("너비"))
        self._width_slider = QSlider(Qt.Orientation.Horizontal)
        self._width_slider.setRange(400, 800)
        self._width_slider.setTickInterval(50)
        self._width_label = QLabel()
        self._width_label.setFixedWidth(50)
        self._width_slider.valueChanged.connect(
            lambda v: self._width_label.setText(f"{v}px")
        )
        self._width_slider.valueChanged.connect(self._emit_preview)
        row_w.addWidget(self._width_slider, 1)
        row_w.addWidget(self._width_label)
        ug_lo.addLayout(row_w)

        # 위치
        row_p = QHBoxLayout()
        row_p.addWidget(QLabel("위치 (상단 %)"))
        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setRange(10, 50)
        self._position_label = QLabel()
        self._position_label.setFixedWidth(50)
        self._position_slider.valueChanged.connect(
            lambda v: self._position_label.setText(f"{v}%")
        )
        self._position_slider.valueChanged.connect(self._emit_preview)
        row_p.addWidget(self._position_slider, 1)
        row_p.addWidget(self._position_label)
        ug_lo.addLayout(row_p)

        # 투명도
        row_o = QHBoxLayout()
        row_o.addWidget(QLabel("투명도"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(150, 255)
        self._opacity_label = QLabel()
        self._opacity_label.setFixedWidth(50)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(str(v))
        )
        self._opacity_slider.valueChanged.connect(self._emit_preview)
        row_o.addWidget(self._opacity_slider, 1)
        row_o.addWidget(self._opacity_label)
        ug_lo.addLayout(row_o)

        # 강조 색상
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("강조 색상"))
        color_row.addStretch()
        self._color_buttons: list[QPushButton] = []
        for hex_color, name in self._COLOR_PRESETS:
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setToolTip(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("hex_color", hex_color)
            btn.clicked.connect(
                lambda checked=False, c=hex_color: self._select_color(c)
            )
            self._color_buttons.append(btn)
            color_row.addWidget(btn)
        ug_lo.addLayout(color_row)

        lo.addWidget(ui_group)

        # ── 동작 섹션 ──
        behavior_group = QGroupBox("동작")
        bg_lo = QVBoxLayout(behavior_group)
        bg_lo.setSpacing(12)

        # 결과 자동 닫힘 시간
        row_ac = QHBoxLayout()
        row_ac.addWidget(QLabel("결과 자동 닫힘"))
        self._autoclose_slider = QSlider(Qt.Orientation.Horizontal)
        self._autoclose_slider.setRange(1, 10)      # 1~10초
        self._autoclose_label = QLabel()
        self._autoclose_label.setFixedWidth(50)
        self._autoclose_slider.valueChanged.connect(
            lambda v: self._autoclose_label.setText(f"{v}초")
        )
        row_ac.addWidget(self._autoclose_slider, 1)
        row_ac.addWidget(self._autoclose_label)
        bg_lo.addLayout(row_ac)

        # 시작 시 자동 실행
        self._autostart_check = QCheckBox("Windows 시작 시 자동 실행")
        self._autostart_check.setStyleSheet(
            f"QCheckBox {{ color: {P.TEXT}; font-size: 13px; spacing: 8px; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; "
            f"border: 1px solid {P.BORDER}; background: {P.BG_CARD}; }}"
            f"QCheckBox::indicator:checked {{ background: {P.ACCENT}; border: none; }}"
        )
        bg_lo.addWidget(self._autostart_check)

        lo.addWidget(behavior_group)

        # ── 버전 / 업데이트 섹션 ──
        ver_group = QGroupBox("버전 정보")
        vg_lo = QHBoxLayout(ver_group)
        vg_lo.setSpacing(12)

        from version import __version__
        ver_label = QLabel(f"현재 버전: v{__version__}")
        ver_label.setStyleSheet(f"color: {P.TEXT}; font-size: 13px;")
        vg_lo.addWidget(ver_label)
        vg_lo.addStretch()

        btn_update_check = QPushButton("업데이트 확인")
        btn_update_check.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update_check.setStyleSheet(
            f"QPushButton {{ background: {P.BG_HOVER}; color: {P.TEXT_BRIGHT}; "
            f"border: 1px solid {P.BORDER}; border-radius: 8px; "
            f"padding: 6px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {P.ACCENT}; color: {P.ACCENT_TEXT}; }}"
        )
        btn_update_check.clicked.connect(self._check_update_manual)
        vg_lo.addWidget(btn_update_check)

        lo.addWidget(ver_group)

        lo.addStretch()

        # 저장 버튼
        footer = QHBoxLayout()
        footer.addStretch()
        btn_save = QPushButton("Save Preferences")
        btn_save.setObjectName("save_btn")
        btn_save.setFixedSize(180, 44)
        btn_save.clicked.connect(self._save_preferences)
        footer.addWidget(btn_save)
        lo.addLayout(footer)

        # 현재 값 로드
        self._load_prefs_to_ui()

        return canvas

    def _build_editor_page(self) -> QFrame:
        """단축키 에디터 페이지 (우측 패널)."""
        canvas = QFrame()
        canvas.setObjectName("EditorCanvas")
        right = QVBoxLayout(canvas)
        right.setContentsMargins(28, 28, 28, 28)
        right.setSpacing(20)

        # 헤더: 라벨 + 키워드 제목 입력
        header = QVBoxLayout()
        header.setSpacing(4)
        kw_lbl = QLabel("KEYWORD")
        kw_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 800; "
            f"letter-spacing: 2px; color: {P.ACCENT};"
        )
        header.addWidget(kw_lbl)

        self._keyword_edit = QLineEdit()
        self._keyword_edit.setObjectName("keyword_title")
        self._keyword_edit.setPlaceholderText("Spotlight에 입력할 키워드")
        header.addWidget(self._keyword_edit)
        right.addLayout(header)

        # 명령 시퀀스 섹션
        seq_lbl = QLabel("SEQUENCE")
        seq_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1px; color: {P.TEXT_DIM};"
        )
        right.addWidget(seq_lbl)

        self._cmd_list = QListWidget()
        self._cmd_list.setObjectName("cmd_sequence")
        self._cmd_list.setFixedHeight(130)
        right.addWidget(self._cmd_list)

        self._btn_del_cmd = QPushButton("선택 명령 삭제")
        self._btn_del_cmd.setObjectName("delete_btn")
        self._btn_del_cmd.clicked.connect(self._delete_command)
        right.addWidget(self._btn_del_cmd)

        # 명령 추가 피커 (탭)
        picker_lbl = QLabel("ADD COMMAND")
        picker_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1px; color: {P.TEXT_DIM};"
        )
        right.addWidget(picker_lbl)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_layout_tab(), "화면 배치")
        self._tabs.addTab(self._build_app_site_tab(), "앱 / 사이트")
        self._tabs.addTab(self._build_system_tab(), "시스템 정보")
        right.addWidget(self._tabs, 1)

        # 저장 버튼 (우측 정렬)
        footer = QHBoxLayout()
        footer.addStretch()
        self._btn_save = QPushButton("Save Changes")
        self._btn_save.setObjectName("save_btn")
        self._btn_save.setFixedSize(160, 44)
        self._btn_save.clicked.connect(self._save_current)
        footer.addWidget(self._btn_save)
        right.addLayout(footer)

        return canvas

    def _show_general_page(self):
        """사이드바 '일반 설정' 클릭 → 일반 페이지 표시 + 미리보기."""
        self._keyword_list.clearSelection()
        self._right_stack.setCurrentIndex(0)
        self._update_sidebar_style()
        self.preview_requested.emit(True)

    def _show_editor_page(self):
        """단축키 선택 시 에디터 페이지 표시."""
        self._right_stack.setCurrentIndex(1)
        self._update_sidebar_style()
        self.preview_requested.emit(False)

    def _update_sidebar_style(self):
        """현재 페이지에 따라 '일반 설정' 버튼 스타일 토글."""
        if self._right_stack.currentIndex() == 0:
            self._btn_general.setStyleSheet(
                f"QPushButton {{ background: {P.BG_CARD}; color: {P.TEXT_BRIGHT}; "
                f"border: 1px solid {P.ACCENT}; border-radius: 8px; "
                f"padding: 10px 12px; font-size: 13px; font-weight: 600; text-align: left; }}"
            )
        else:
            self._btn_general.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {P.TEXT}; "
                f"border: 1px solid {P.BORDER}; border-radius: 8px; "
                f"padding: 10px 12px; font-size: 13px; text-align: left; }}"
                f"QPushButton:hover {{ background: {P.BG_HOVER}; }}"
            )

    # ── 일반 탭 ──

    # QKeySequenceEdit → "Ctrl+Space" 형식 변환
    @staticmethod
    def _key_seq_to_str(seq: QKeySequence) -> str:
        """QKeySequence → 'Ctrl+Space' 형식 문자열."""
        s = seq.toString(QKeySequence.SequenceFormat.NativeText)
        # Qt가 반환하는 형식 정리 (ex: "Ctrl+Space" 이미 올바름)
        return s if s else ""

    _COLOR_PRESETS = [
        ("#6366f1", "인디고"),
        ("#3b82f6", "파랑"),
        ("#10b981", "초록"),
        ("#ef4444", "빨강"),
        ("#8b5cf6", "보라"),
        ("#f97316", "주황"),
    ]

    def _load_prefs_to_ui(self):
        """현재 preferences를 UI 위젯에 반영."""
        p = self._prefs

        self._hotkey_spotlight_edit.setKeySequence(
            QKeySequence(p.get("hotkey_spotlight", "Ctrl+Space"))
        )
        self._hotkey_voice_edit.setKeySequence(
            QKeySequence(p.get("hotkey_voice", "Alt+Space"))
        )

        self._width_slider.setValue(p.get("spotlight_width", 600))
        self._width_label.setText(f"{self._width_slider.value()}px")

        self._position_slider.setValue(p.get("spotlight_position", 22))
        self._position_label.setText(f"{self._position_slider.value()}%")

        self._opacity_slider.setValue(p.get("spotlight_opacity", 230))
        self._opacity_label.setText(str(self._opacity_slider.value()))

        self._update_color_buttons(p.get("accent_color", "#6366f1"))

        ac_sec = p.get("result_auto_close_ms", 4000) // 1000
        self._autoclose_slider.setValue(max(1, min(10, ac_sec)))
        self._autoclose_label.setText(f"{self._autoclose_slider.value()}초")

        self._autostart_check.setChecked(p.get("auto_start", False))

    def _emit_preview(self, _value=None):
        """슬라이더 변경 시 실시간 미리보기 emit."""
        preview = dict(self._prefs)
        preview["spotlight_width"] = self._width_slider.value()
        preview["spotlight_position"] = self._position_slider.value()
        preview["spotlight_opacity"] = self._opacity_slider.value()
        self.preferences_changed.emit(preview)

    def _select_color(self, hex_color: str):
        """색상 프리셋 클릭."""
        self._prefs["accent_color"] = hex_color
        self._update_color_buttons(hex_color)
        self._emit_preview()

    def _update_color_buttons(self, selected: str):
        """색상 버튼 스타일 갱신 (선택된 색상에 테두리)."""
        for btn in self._color_buttons:
            c = btn.property("hex_color")
            if c == selected:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {c}; border: 3px solid {P.TEXT_BRIGHT}; "
                    f"border-radius: 16px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {c}; border: 2px solid transparent; "
                    f"border-radius: 16px; }}"
                    f"QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.3); }}"
                )

    def _save_preferences(self):
        """일반 탭 설정 저장 (핫키 포함) + 파일 기록."""
        # 핫키 읽기 (핫키는 저장 시에만 반영)
        sp_seq = self._hotkey_spotlight_edit.keySequence()
        vo_seq = self._hotkey_voice_edit.keySequence()
        sp_str = self._key_seq_to_str(sp_seq) or self._prefs.get("hotkey_spotlight", "Ctrl+Space")
        vo_str = self._key_seq_to_str(vo_seq) or self._prefs.get("hotkey_voice", "Alt+Space")

        self._prefs["hotkey_spotlight"] = sp_str
        self._prefs["hotkey_voice"] = vo_str
        self._prefs["spotlight_width"] = self._width_slider.value()
        self._prefs["spotlight_position"] = self._position_slider.value()
        self._prefs["spotlight_opacity"] = self._opacity_slider.value()
        # accent_color는 _select_color에서 이미 업데이트됨
        self._prefs["result_auto_close_ms"] = self._autoclose_slider.value() * 1000
        self._prefs["auto_start"] = self._autostart_check.isChecked()

        save_preferences(self._prefs)
        self._apply_auto_start(self._prefs["auto_start"])
        self.preferences_changed.emit(dict(self._prefs))

        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")

    def _check_update_manual(self):
        """수동 업데이트 확인 버튼 클릭."""
        from utils.updater import check_for_update
        result = check_for_update()
        if result:
            new_version, download_url, release_notes = result
            from ui.update_dialog import UpdateDialog
            dlg = UpdateDialog(new_version, download_url, release_notes, parent=self)
            dlg.exec()
        else:
            QMessageBox.information(self, "업데이트 확인", "현재 최신 버전입니다.")

    @staticmethod
    def _apply_auto_start(enabled: bool):
        """Windows 시작프로그램 레지스트리 등록/해제."""
        import sys
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                # frozen exe면 exe 경로, 아니면 python + main.py
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    import os
                    main_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "main.py",
                    )
                    cmd = f'"{sys.executable}" "{main_path}"'
                winreg.SetValueEx(key, "NexusShell", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "NexusShell")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[자동 실행 설정 오류] {e}")

    # ── 피커 탭 빌드 ──

    def _build_layout_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 레이아웃 타입 선택
        type_row = QHBoxLayout()
        type_row.setSpacing(6)

        self._btn_split = QPushButton("◫ 좌우 분할")
        self._btn_split.setObjectName("picker_btn")
        self._btn_split.setStyleSheet(
            self._btn_split.styleSheet() + "min-height: 32px; min-width: 70px; padding: 4px 10px;")
        self._btn_split.setCheckable(True)
        self._btn_split.setChecked(True)
        self._btn_split.clicked.connect(lambda: self._set_layout("split"))

        self._btn_single = QPushButton("⬜ 전체 화면")
        self._btn_single.setObjectName("picker_btn")
        self._btn_single.setStyleSheet(
            self._btn_single.styleSheet() + "min-height: 32px; min-width: 70px; padding: 4px 10px;")
        self._btn_single.setCheckable(True)
        self._btn_single.clicked.connect(lambda: self._set_layout("single"))

        type_row.addWidget(self._btn_split)
        type_row.addWidget(self._btn_single)
        type_row.addStretch()
        layout.addLayout(type_row)

        # 모니터 에디터
        self._monitor = MonitorLayoutWidget()
        self._monitor.setMinimumHeight(120)
        layout.addWidget(self._monitor, 1)

        # 적용 버튼
        btn_apply = QPushButton("↑ 명령에 추가")
        btn_apply.setObjectName("apply_btn")
        btn_apply.setFixedHeight(32)
        btn_apply.clicked.connect(self._apply_layout)
        layout.addWidget(btn_apply)

        return widget

    def _set_layout(self, layout_type: str):
        self._btn_split.setChecked(layout_type == "split")
        self._btn_single.setChecked(layout_type == "single")
        self._monitor.set_layout_type(layout_type)

    def _apply_layout(self):
        if not self._monitor.has_assignments():
            QMessageBox.warning(self, "알림", "모니터에 앱을 배치해주세요.")
            return
        commands = self._monitor.get_commands()
        for cmd in commands:
            display = self._display_for_cmd(cmd)
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._cmd_list.addItem(item)
        self._monitor.reset()

    def _build_app_site_tab(self) -> QWidget:
        widget = QWidget()
        lo = QVBoxLayout(widget)
        lo.setContentsMargins(8, 8, 8, 0)
        lo.setSpacing(8)

        # URL 직접 입력 행 + 앱 추가 버튼
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://example.com")
        self._url_input.returnPressed.connect(self._add_custom_url)
        url_row.addWidget(self._url_input)

        btn_add_url = QPushButton("추가")
        btn_add_url.setObjectName("apply_btn")
        btn_add_url.setFixedWidth(60)
        btn_add_url.clicked.connect(self._add_custom_url)
        url_row.addWidget(btn_add_url)

        btn_add_app = QPushButton("➕ 앱 추가")
        btn_add_app.setObjectName("apply_btn")
        btn_add_app.setFixedWidth(90)
        btn_add_app.clicked.connect(self._open_app_picker)
        url_row.addWidget(btn_add_app)

        lo.addLayout(url_row)

        # user app 이름 집합 로드 (우클릭 삭제 판별용)
        user_apps_raw = load_user_apps_raw()
        self._user_app_names = {k.lower() for k in user_apps_raw}

        # 앱 + 사이트 통합 그리드
        app_items = _unique_items(APP_ALIASES, APP_DISPLAY)
        site_items = _unique_items(SITE_ALIASES, SITE_DISPLAY)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        self._app_grid = QGridLayout(container)
        self._app_grid.setSpacing(10)

        idx = 0
        for name, icon in app_items:
            btn = QPushButton(f"{icon}\n{name}")
            btn.setObjectName("picker_btn")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cmd = {"function": "run_app", "arguments": {"app_name": name}}
            display = f"{icon} {name}"
            btn.clicked.connect(
                lambda checked=False, c=cmd, d=display: self._add_cmd(c, d))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            if name.lower() in self._user_app_names:
                btn.customContextMenuRequested.connect(
                    lambda _pos, n=name, b=btn: self._show_app_context_menu(n, b))
            else:
                btn.customContextMenuRequested.connect(
                    lambda _pos, n=name, t="app": self._show_fav_only_menu(n, t))
            self._app_grid.addWidget(btn, idx // GRID_COLS, idx % GRID_COLS)
            idx += 1

        for name, icon in site_items:
            btn = QPushButton(f"{icon}\n{name}")
            btn.setObjectName("picker_btn")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cmd = {"function": "open_url", "arguments": {"site_name": name}}
            display = f"{icon} {name}"
            btn.clicked.connect(
                lambda checked=False, c=cmd, d=display: self._add_cmd(c, d))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _pos, n=name, t="url": self._show_fav_only_menu(n, t))
            self._app_grid.addWidget(btn, idx // GRID_COLS, idx % GRID_COLS)
            idx += 1

        self._app_grid_idx = idx

        scroll.setWidget(container)
        lo.addWidget(scroll, 1)

        return widget

    def _open_app_picker(self):
        dlg = AppPickerDialog(self)
        dlg.apps_selected.connect(self._on_apps_picked)
        dlg.exec()

    def _on_apps_picked(self, selected: dict[str, str]):
        for name, path in selected.items():
            add_user_app(name, path)
            self._user_app_names.add(name.lower())
            # 그리드에 버튼 동적 추가
            icon = APP_DISPLAY.get(name.lower(), "▪️")
            btn = QPushButton(f"{icon}\n{name}")
            btn.setObjectName("picker_btn")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cmd = {"function": "run_app", "arguments": {"app_name": name.lower()}}
            display = f"{icon} {name}"
            btn.clicked.connect(
                lambda checked=False, c=cmd, d=display: self._add_cmd(c, d))
            # 우클릭 삭제 메뉴 연결
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _pos, n=name, b=btn: self._show_app_context_menu(n, b))
            self._app_grid.addWidget(
                btn,
                self._app_grid_idx // GRID_COLS,
                self._app_grid_idx % GRID_COLS,
            )
            self._app_grid_idx += 1

    def _show_fav_only_menu(self, name: str, fav_type: str):
        """기본 앱/사이트의 '즐겨찾기 추가' 메뉴."""
        menu = QMenu(self)
        action = menu.addAction("즐겨찾기 추가")
        if menu.exec(QCursor.pos()) == action:
            if fav_type == "app":
                target = APP_ALIASES.get(name.lower(), name)
            else:
                target = SITE_ALIASES.get(name.lower(), name)
            self._favorites.add(name, fav_type, target)

    def _show_app_context_menu(self, app_name: str, btn: QPushButton):
        """사용자 등록 앱의 우클릭 메뉴 (즐겨찾기 추가 + 삭제)."""
        menu = QMenu(self)
        fav_action = menu.addAction("즐겨찾기 추가")
        del_action = menu.addAction("삭제")
        chosen = menu.exec(QCursor.pos())
        if chosen == fav_action:
            target = APP_ALIASES.get(app_name.lower(), app_name)
            self._favorites.add(app_name, "app", target)
        elif chosen == del_action:
            remove_user_app(app_name)
            btn.setParent(None)
            self._user_app_names.discard(app_name.lower())

    def _add_custom_url(self):
        raw = self._url_input.text().strip()
        if not raw:
            return
        # 프로토콜 자동 접두어
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        cmd = {"function": "open_url", "arguments": {"url": raw}}
        # 표시용: 30자 초과 시 말줄임
        label = raw if len(raw) <= 30 else raw[:30] + "…"
        self._add_cmd(cmd, f"🌐 {label}")
        self._url_input.clear()

    def _build_system_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(10)

        for idx, (key, icon, display_name) in enumerate(SYSTEM_OPTIONS):
            btn = QPushButton(f"{icon}\n{display_name}")
            btn.setObjectName("picker_btn")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cmd = {"function": "check_system", "arguments": {"info_type": key}}
            btn.clicked.connect(
                lambda checked=False, c=cmd, d=f"{icon} {display_name}": self._add_cmd(c, d))
            grid.addWidget(btn, idx // GRID_COLS, idx % GRID_COLS)

        scroll.setWidget(container)
        lo = QVBoxLayout(widget)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(scroll)
        return widget

    def _build_picker_grid(self, items, func, arg_key):
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(10)

        for idx, (name, icon) in enumerate(items):
            btn = QPushButton(f"{icon}\n{name}")
            btn.setObjectName("picker_btn")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cmd = {"function": func, "arguments": {arg_key: name}}
            display = f"{icon} {name}"
            btn.clicked.connect(
                lambda checked=False, c=cmd, d=display: self._add_cmd(c, d))
            grid.addWidget(btn, idx // GRID_COLS, idx % GRID_COLS)

        scroll.setWidget(container)
        lo = QVBoxLayout(widget)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(scroll)
        return widget

    # ══════════════════════════════════════════
    # 키워드 목록
    # ══════════════════════════════════════════

    def _refresh_keyword_list(self):
        self._keyword_list.clear()
        for keyword in self._manager.get_all():
            self._keyword_list.addItem(keyword)
        self._clear_editor()

    def _on_keyword_selected(self, current: QListWidgetItem, _previous):
        if current is None:
            self._clear_editor()
            return
        self._show_editor_page()
        keyword = current.text()
        self._current_keyword = keyword
        self._keyword_edit.setText(keyword)

        commands = self._manager.get_all().get(keyword, [])
        self._cmd_list.clear()
        for cmd in commands:
            item = QListWidgetItem(self._display_for_cmd(cmd))
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._cmd_list.addItem(item)

    def _clear_editor(self):
        self._current_keyword = None
        self._keyword_edit.clear()
        self._cmd_list.clear()

    def _add_keyword(self):
        self._keyword_list.clearSelection()
        self._clear_editor()
        self._keyword_edit.setFocus()

    def _delete_keyword(self):
        item = self._keyword_list.currentItem()
        if item is None:
            return
        keyword = item.text()
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{keyword}' 단축키를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._manager.remove(keyword)
            self._refresh_keyword_list()
            self.shortcuts_updated.emit()

    # ══════════════════════════════════════════
    # 명령 편집
    # ══════════════════════════════════════════

    def _add_cmd(self, cmd: dict, display: str):
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, cmd)
        self._cmd_list.addItem(item)

    def _delete_command(self):
        row = self._cmd_list.currentRow()
        if row >= 0:
            self._cmd_list.takeItem(row)

    @staticmethod
    def _display_for_cmd(cmd: dict) -> str:
        func = cmd.get("function", "")
        args = cmd.get("arguments", {})

        if func == "run_app":
            name = args.get("app_name", "?")
            icon = APP_DISPLAY.get(name, "▪️")
            return f"{icon} {name}"
        elif func == "open_url":
            name = args.get("site_name", args.get("url", "?"))
            icon = SITE_DISPLAY.get(name, "🌐")
            if len(name) > 30:
                name = name[:30] + "…"
            return f"{icon} {name}"
        elif func == "check_system":
            info = args.get("info_type", "?")
            for key, icon, display_name in SYSTEM_OPTIONS:
                if key == info:
                    return f"{icon} {display_name}"
            return f"📊 {info}"
        elif func == "launch_and_snap":
            pos = args.get("position", "?")
            name = args.get("app_name", args.get("site_name", "?"))
            icon = APP_DISPLAY.get(name, SITE_DISPLAY.get(name, "▪️"))
            pos_label = dict((k, l) for k, _, l in SNAP_OPTIONS).get(pos, pos)
            return f"{icon} {name}  →  {pos_label}"
        elif func == "general_response":
            msg = args.get("message", "")
            return f"💬 {msg}"
        return f"▪️ {func}"

    # ══════════════════════════════════════════
    # 저장
    # ══════════════════════════════════════════

    def _save_current(self):
        keyword = self._keyword_edit.text().strip()
        if not keyword:
            QMessageBox.warning(self, "경고", "키워드를 입력하세요.")
            return

        if self._cmd_list.count() == 0:
            QMessageBox.warning(self, "경고", "최소 하나의 명령을 추가하세요.")
            return

        commands = []
        for i in range(self._cmd_list.count()):
            cmd = self._cmd_list.item(i).data(Qt.ItemDataRole.UserRole)
            commands.append(cmd)

        if self._current_keyword and self._current_keyword != keyword:
            self._manager.remove(self._current_keyword)

        self._manager.add(keyword, commands)
        self._current_keyword = keyword
        self._refresh_keyword_list()
        self.shortcuts_updated.emit()

        for i in range(self._keyword_list.count()):
            if self._keyword_list.item(i).text() == keyword:
                self._keyword_list.setCurrentRow(i)
                break

        QMessageBox.information(self, "저장 완료", f"'{keyword}' 단축키가 저장되었습니다.")
