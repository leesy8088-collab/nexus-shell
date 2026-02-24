"""
NexusApp: 전체 조율 (tray + spotlight + worker + hotkey + voice)
"""

import sys
import threading
import winsound
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage

import re
from config import APP_ALIASES, SITE_ALIASES, SITE_SEARCH, load_preferences, save_preferences
from utils.app_scanner import load_user_apps
from utils.favorites import FavoritesManager
from utils.clipboard_history import ClipboardHistoryManager
from utils.open_windows import get_open_windows, get_browser_tabs, focus_window
from utils.history import HistoryManager
from core.brain_router import BrainRouter
from core.executor import Executor
from core.shortcuts import ShortcutManager
from core.stt import STTEngine
from ui.tray import TrayManager
from ui.spotlight import SpotlightWindow
from ui.worker import BrainWorker
from ui.shortcut_worker import ShortcutWorker
from ui.voice_worker import VoiceWorker
from ui.settings_window import SettingsWindow
from ui.hotkey import HotkeyListener


class NexusApp:
    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("Nexus Shell")

        # core 인스턴스
        self._brain = BrainRouter()
        self._executor = Executor()
        self._shortcut_manager = ShortcutManager()
        self._stt_engine = STTEngine()
        self._update_stt_hints()
        self._stt_engine.preload()
        self._worker = None

        # 명령 히스토리
        self._history = HistoryManager()

        # 음성 상태
        self._voice_worker = None
        self._is_voice_recording = False

        # 개인화 설정
        self._prefs = load_preferences()

        # UI 컴포넌트
        self._tray = TrayManager()
        self._spotlight = SpotlightWindow(preferences=self._prefs)
        self._hotkey = HotkeyListener()
        self._settings_window = None

        # 즐겨찾기
        self._favorites = FavoritesManager()
        self._icon_workers: list[QThread] = []

        # 클립보드 히스토리
        self._clipboard_history = ClipboardHistoryManager()
        self._clipboard_monitoring = True

        self._connect_signals()
        self._setup_clipboard_monitor()

        # user_apps.json → APP_ALIASES 로드 (캐시 읽기만, 즉시 완료)
        load_user_apps()
        self._favorites.load_urls_into_aliases()
        self._update_stt_hints()

    def _connect_signals(self):
        # 핫키 → Spotlight 토글 (즐겨찾기 전달)
        self._hotkey.hotkey_pressed.connect(self._on_spotlight_toggle)

        # 음성 핫키 → 녹음 토글
        self._hotkey.voice_hotkey_pressed.connect(self._on_voice_hotkey)

        # 트레이 → Spotlight 열기 / 설정 / 앱 종료
        self._tray.open_requested.connect(self._on_spotlight_toggle)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.exit_requested.connect(self._quit)

        # Spotlight 입력 → Worker 시작
        self._spotlight.input_submitted.connect(self._on_input_submitted)

        # Spotlight 히스토리 순회
        self._spotlight.history_prev_requested.connect(self._on_history_prev)
        self._spotlight.history_next_requested.connect(self._on_history_next)

        # Spotlight 녹음 취소
        self._spotlight.recording_cancel_requested.connect(self._cancel_voice)

        # 즐겨찾기
        self._spotlight.favorite_clicked.connect(self._on_favorite_clicked)
        self._spotlight.favorite_add_requested.connect(self._on_favorite_add)
        self._spotlight.favorite_remove_requested.connect(self._on_favorite_remove)

        # 클립보드
        self._spotlight.clipboard_item_clicked.connect(self._on_clipboard_item_clicked)
        self._spotlight.clipboard_item_remove_requested.connect(self._on_clipboard_item_remove)

        # 열린 창
        self._spotlight.window_clicked.connect(self._on_window_clicked)

    def _on_spotlight_toggle(self):
        """Spotlight 토글 시 즐겨찾기 + 클립보드 + 열린 창 전달."""
        self._favorites.reload()
        self._spotlight.set_favorites(self._favorites.get_all())
        self._spotlight.set_clipboard_items(self._clipboard_history.get_all())
        # 열린 창 + 브라우저 탭
        windows = get_open_windows()
        browser_tabs = get_browser_tabs()
        self._spotlight.set_windows_items(browser_tabs + windows)
        self._spotlight.toggle()

    # ── 즐겨찾기 핸들러 ──

    def _on_favorite_clicked(self, fav: dict):
        """즐겨찾기 클릭 → 실행."""
        if fav["type"] == "app":
            self._spotlight.show_loading()
            result = self._executor.run_app(fav["name"].lower())
            self._spotlight.show_result(result)
        elif fav["type"] == "url":
            self._spotlight.show_loading()
            result = self._executor.open_url(url=fav["target"])
            self._spotlight.show_result(result)

    def _on_favorite_add(self):
        """'+' 버튼 → URL 등록 다이얼로그."""
        dlg = QDialog(self._spotlight)
        dlg.setWindowTitle("즐겨찾기 추가")
        dlg.setFixedSize(360, 180)
        dlg.setStyleSheet(
            "QDialog { background: rgba(30,30,30,245); color: #fff; }"
            "QLineEdit { background: rgba(50,50,50,220); color: #fff; "
            "  border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; "
            "  padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid rgba(80,140,255,0.6); }"
            "QLabel { color: #aaa; font-size: 12px; background: transparent; }"
            "QPushButton { background: #6366f1; color: #fff; border: none; "
            "  border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #818cf8; }"
        )
        lo = QVBoxLayout(dlg)
        lo.setSpacing(8)

        lo.addWidget(QLabel("이름"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("예: ChatGPT")
        lo.addWidget(name_input)

        lo.addWidget(QLabel("URL"))
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://chat.openai.com")
        lo.addWidget(url_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("추가")
        btn_row.addWidget(btn_ok)
        lo.addLayout(btn_row)

        def _do_add():
            name = name_input.text().strip()
            url = url_input.text().strip()
            if not name or not url:
                return
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            item = self._favorites.add(name, "url", url)
            self._favorites.load_urls_into_aliases()
            self._update_stt_hints()
            self._spotlight.set_favorites(self._favorites.get_all())
            # 아이콘 백그라운드 fetch
            self._start_icon_fetch(item)
            dlg.accept()

        btn_ok.clicked.connect(_do_add)
        url_input.returnPressed.connect(_do_add)
        dlg.exec()

    def _on_favorite_remove(self, name: str):
        """즐겨찾기 삭제."""
        self._favorites.remove(name)
        self._spotlight.set_favorites(self._favorites.get_all())

    # ── 클립보드 모니터링 ──

    def _setup_clipboard_monitor(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if not self._clipboard_monitoring:
            return
        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                from PySide6.QtCore import QBuffer, QIODevice
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buf, "PNG")
                png_bytes = bytes(buf.data())
                buf.close()
                self._clipboard_history.add_image(png_bytes)
        elif mime.hasText():
            text = clipboard.text()
            if text.strip():
                self._clipboard_history.add_text(text)

    def _on_clipboard_item_clicked(self, item_id: str):
        """클립보드 항목 클릭 → 재복사 + 닫기."""
        item_type, data = self._clipboard_history.get_data(item_id)
        if data is None:
            return
        self._clipboard_monitoring = False  # 재복사 시 다시 기록 방지
        clipboard = QGuiApplication.clipboard()
        if item_type == "text":
            clipboard.setText(data)
        else:
            image = QImage()
            image.loadFromData(data, "PNG")
            clipboard.setImage(image)
        self._clipboard_monitoring = True
        self._spotlight._dismiss()

    def _on_clipboard_item_remove(self, item_id: str):
        """클립보드 항목 삭제."""
        self._clipboard_history.remove(item_id)
        self._spotlight.set_clipboard_items(self._clipboard_history.get_all())

    # ── 열린 창 핸들러 ──

    def _on_window_clicked(self, hwnd: int):
        """열린 창 클릭 → 포커스 전환 + 닫기."""
        self._spotlight._dismiss()
        focus_window(hwnd)

    def _start_icon_fetch(self, item: dict):
        """아이콘 백그라운드 fetch 워커 시작."""
        worker = _IconFetchWorker(self._favorites, item)
        worker.finished_signal.connect(self._on_icon_fetched)
        worker.finished.connect(lambda: self._icon_workers.remove(worker) if worker in self._icon_workers else None)
        self._icon_workers.append(worker)
        worker.start()

    def _on_icon_fetched(self, name: str, icon_path: str):
        """아이콘 fetch 완료 → 즐겨찾기 갱신."""
        if icon_path:
            self._spotlight.set_favorites(self._favorites.get_all())

    def _update_stt_hints(self):
        """앱/사이트 별칭만 STT 힌트로 설정 (단축어 제외 — 환각 방지)"""
        keywords = list(APP_ALIASES.keys())
        keywords += list(SITE_ALIASES.keys())
        # 중복 제거
        self._stt_engine.set_hints(list(dict.fromkeys(keywords)))

    def _on_input_submitted(self, text):
        self._history.add(text)

        # 1. 단축키 매칭 확인
        commands = self._shortcut_manager.match(text)
        if commands:
            self._spotlight.show_loading()
            self._worker = ShortcutWorker(self._executor, commands)
            self._worker.result_ready.connect(self._on_shortcut_result)
            self._worker.error_occurred.connect(self._on_error)
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker.start()
            return

        # 2. 앱/사이트 별칭 즉시 매칭 (LLM 스킵)
        key = text.strip().lower()
        if key in APP_ALIASES:
            self._spotlight.show_loading()
            result = self._executor.run_app(key)
            self._spotlight.show_result(result)
            return
        if key in SITE_ALIASES:
            self._spotlight.show_loading()
            result = self._executor.open_url(site_name=key)
            self._spotlight.show_result(result)
            return

        # 3. 패턴 매칭 (LLM 스킵)
        result = self._try_pattern_match(text)
        if result is not None:
            self._spotlight.show_loading()
            self._spotlight.show_result(result)
            return

        # 4. 미매칭 → 기존 BrainWorker(LLM) 경로
        self._spotlight.show_loading()
        self._worker = BrainWorker(self._brain, self._executor, text)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    # ── 히스토리 순회 ──

    def _on_history_prev(self, current_text: str):
        cmd = self._history.previous(current_text)
        if cmd is not None:
            self._spotlight.set_input_text(cmd)

    def _on_history_next(self):
        cmd = self._history.next()
        if cmd is not None:
            self._spotlight.set_input_text(cmd)

    # ── 패턴 매칭 ──

    _APP_SUFFIXES = re.compile(
        r"^(.+?)\s*(?:켜줘|켜|열어줘|열어|실행해줘|실행해|실행|띄워줘|띄워)$"
    )
    _SITE_SEARCH_PATTERN = re.compile(
        r"^(.+?)(?:에서|에)\s+(.+?)\s*(?:검색해줘|검색해|검색|찾아줘|찾아)$"
    )
    _SEARCH_PATTERN = re.compile(
        r"^(.+?)\s*(?:검색해줘|검색해|검색|찾아줘|찾아)$"
    )
    _DIAGNOSE_PATTERN = re.compile(
        r"(?:컴퓨터|시스템|PC|pc)\s*(?:왜|뭐가|뭐)?\s*(?:느려|느린|느릴|상태|진단)"
        r"|(?:왜|뭐가)\s*(?:이렇게\s*)?느려"
        r"|시스템\s*진단"
        r"|컴퓨터\s*상태",
        re.IGNORECASE,
    )

    def _try_pattern_match(self, text: str) -> str | None:
        """자연어 패턴 매칭. 매칭되면 결과 문자열, 아니면 None."""
        stripped = text.strip()

        # "컴퓨터 왜 느려", "시스템 진단", "PC 느려" 등 → 시스템 진단
        if self._DIAGNOSE_PATTERN.search(stripped):
            return self._executor.check_system("diagnose")

        # "유튜브에서 고양이 검색해줘" → 사이트 내 검색
        m = self._SITE_SEARCH_PATTERN.match(stripped)
        if m:
            site, query = m.group(1).strip(), m.group(2).strip()
            site_key = site.lower()
            if site_key in SITE_ALIASES:
                return self._executor.open_url(site_name=site_key, search_query=query)

        # "크롬 켜줘", "유튜브 열어" → 앱 또는 사이트 실행
        m = self._APP_SUFFIXES.match(stripped)
        if m:
            name = m.group(1).strip().lower()
            if name in APP_ALIASES:
                return self._executor.run_app(name)
            if name in SITE_ALIASES:
                return self._executor.open_url(site_name=name)

        # "날씨 검색해줘" → 웹 검색
        m = self._SEARCH_PATTERN.match(stripped)
        if m:
            query = m.group(1).strip()
            # 사이트 이름이면 사이트 열기로 처리
            if query.lower() in SITE_ALIASES:
                return self._executor.open_url(site_name=query.lower())
            return self._executor.open_url(search_query=query)

        # "유튜브 고양이" → 사이트명 + 검색어 (접미사 없는 자유 형태)
        words = stripped.split(None, 1)
        if len(words) == 2:
            site_key = words[0].lower()
            if site_key in SITE_ALIASES:
                return self._executor.open_url(site_name=site_key, search_query=words[1])

        return None

    def _on_shortcut_result(self, result_text):
        self._spotlight.show_result(f"[단축키]\n{result_text}")

    def _on_result(self, func_name, result_text):
        display = f"[{func_name}]\n{result_text}"
        self._spotlight.show_result(display)

    def _on_error(self, error_msg):
        self._spotlight.show_error(error_msg)

    # ── 음성 입력 ──

    @staticmethod
    def _beep(freq: int, duration: int = 80):
        """비차단 비프음"""
        threading.Thread(
            target=winsound.Beep, args=(freq, duration), daemon=True
        ).start()

    def _on_voice_hotkey(self):
        """Alt+Space 토글: 녹음 시작 ↔ 녹음 중지"""
        if self._is_voice_recording:
            self._stop_voice_recording()
        else:
            self._start_voice_recording()

    def _start_voice_recording(self):
        """VoiceWorker 생성 및 녹음 시작"""
        self._beep(800)  # 높은 톤 — 녹음 시작
        self._is_voice_recording = True
        self._spotlight.show_recording()

        self._voice_worker = VoiceWorker(self._stt_engine)
        self._voice_worker.level_updated.connect(self._spotlight.update_level)
        self._voice_worker.recording_stopped.connect(self._on_recording_auto_stopped)
        self._voice_worker.transcription_ready.connect(self._on_transcription)
        self._voice_worker.error_occurred.connect(self._on_voice_error)
        self._voice_worker.finished.connect(self._voice_worker.deleteLater)
        self._voice_worker.start()

    def _stop_voice_recording(self):
        """녹음 중지 → STT 처리 (수동)"""
        self._beep(500, 60)  # 낮은 톤 — 녹음 종료
        self._is_voice_recording = False
        self._spotlight.show_transcribing()
        if self._voice_worker:
            self._voice_worker.stop_recording()

    def _on_recording_auto_stopped(self):
        """침묵 감지로 자동 중지 시 UI 전환"""
        self._beep(500, 60)  # 낮은 톤 — 녹음 종료
        self._is_voice_recording = False
        self._spotlight.show_transcribing()

    def _cancel_voice(self):
        """녹음 취소 (ESC)"""
        self._is_voice_recording = False
        if self._voice_worker:
            self._voice_worker.cancel()
            self._voice_worker = None
        self._spotlight.stop_recording_ui()
        self._spotlight._dismiss()

    def _on_transcription(self, text):
        """STT 완료 → 기존 파이프라인에 전달"""
        self._is_voice_recording = False
        self._voice_worker = None
        self._spotlight.stop_recording_ui()
        self._on_input_submitted(text)

    def _on_voice_error(self, msg):
        """음성 오류 처리"""
        self._beep(300, 120)  # 낮은 톤 길게 — 에러
        self._is_voice_recording = False
        self._voice_worker = None
        self._spotlight.stop_recording_ui()
        self._spotlight.show_error(msg)

    # ── 설정 / 종료 ──

    def _on_preview_requested(self, show: bool):
        """설정 창에서 미리보기 요청."""
        if show:
            self._spotlight.show_preview()
        else:
            self._spotlight.hide_preview()

    def _on_preferences_changed(self, prefs: dict):
        """설정 창에서 개인화 옵션 변경 시 호출 (미리보기 + 저장 모두)."""
        # Spotlight UI 실시간 업데이트 (미리보기)
        self._spotlight.update_preferences(prefs)

        # 핫키가 변경됐을 때만 재등록 (저장 버튼으로 확정된 경우)
        old_sp = self._prefs.get("hotkey_spotlight")
        old_vo = self._prefs.get("hotkey_voice")
        new_sp = prefs.get("hotkey_spotlight")
        new_vo = prefs.get("hotkey_voice")
        if old_sp != new_sp or old_vo != new_vo:
            self._hotkey.restart(
                new_sp or "Ctrl+Space",
                new_vo or "Alt+Space",
            )

        self._prefs = prefs

    def _open_settings(self):
        try:
            if self._settings_window is None:
                self._settings_window = SettingsWindow(
                    self._shortcut_manager, self._favorites,
                    preferences=self._prefs,
                )
                self._settings_window.shortcuts_updated.connect(
                    self._shortcut_manager.reload
                )
                self._settings_window.shortcuts_updated.connect(
                    self._update_stt_hints
                )
                self._settings_window.preferences_changed.connect(
                    self._on_preferences_changed
                )
                self._settings_window.preview_requested.connect(
                    self._on_preview_requested
                )
            else:
                self._settings_window.set_preferences(self._prefs)
            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.activateWindow()
        except Exception as e:
            print(f"[설정 열기 오류] {e}")
            import traceback; traceback.print_exc()

    def _quit(self):
        self._hotkey.stop()
        if self._voice_worker:
            self._voice_worker.cancel()
            self._voice_worker.wait(2000)
        self._tray.hide()
        self._app.quit()

    def run(self):
        self._tray.show()
        self._hotkey.start(
            self._prefs.get("hotkey_spotlight", "Ctrl+Space"),
            self._prefs.get("hotkey_voice", "Alt+Space"),
        )
        # 3초 후 백그라운드 업데이트 체크
        QTimer.singleShot(3000, self._check_for_update)
        return self._app.exec()

    # ── 자동 업데이트 ──

    def _check_for_update(self):
        """백그라운드 스레드로 업데이트 체크."""
        self._update_worker = _UpdateCheckWorker()
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.finished.connect(self._update_worker.deleteLater)
        self._update_worker.start()

    def _on_update_available(self, new_version, download_url, release_notes):
        """새 버전 발견 → 다이얼로그 표시."""
        from ui.update_dialog import UpdateDialog
        dlg = UpdateDialog(new_version, download_url, release_notes)
        dlg.exec()


class _UpdateCheckWorker(QThread):
    """백그라운드에서 GitHub 업데이트 확인."""
    update_available = Signal(str, str, str)  # new_version, download_url, release_notes

    def run(self):
        try:
            from utils.updater import check_for_update
            result = check_for_update()
            if result:
                self.update_available.emit(*result)
        except Exception as e:
            print(f"[업데이트 체크 오류] {e}")


class _IconFetchWorker(QThread):
    """백그라운드에서 즐겨찾기 아이콘을 가져오는 워커."""
    finished_signal = Signal(str, str)  # name, icon_path

    def __init__(self, favorites_mgr: FavoritesManager, item: dict):
        super().__init__()
        self._fm = favorites_mgr
        self._item = dict(item)  # 복사

    def run(self):
        path = self._fm.fetch_icon(self._item)
        self.finished_signal.emit(self._item["name"], path or "")
