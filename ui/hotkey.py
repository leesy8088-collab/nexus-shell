"""
HotkeyListener: 글로벌 단축키 (설정 기반)
Win32 RegisterHotKey 사용
"""

import ctypes
import ctypes.wintypes
from PySide6.QtCore import QObject, Signal, QAbstractNativeEventFilter, QByteArray
from PySide6.QtWidgets import QApplication

MOD_CTRL = 0x0002
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
HOTKEY_ID = 1
VOICE_HOTKEY_ID = 2

# 수식키 이름 → 비트 매핑
_MOD_MAP = {
    "ctrl": MOD_CTRL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

# 특수 키 이름 → VK 코드
_VK_MAP = {
    "space": 0x20,
    "enter": 0x0D, "return": 0x0D,
    "tab": 0x09,
    "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}


def parse_hotkey_string(s: str) -> tuple[int, int]:
    """
    "Ctrl+Space" 같은 문자열을 (modifiers, vk_code) 로 변환.
    지원: Ctrl, Alt, Shift, Win + 키 이름/문자
    """
    parts = [p.strip().lower() for p in s.split("+")]
    modifiers = 0
    vk = 0

    for part in parts:
        if part in _MOD_MAP:
            modifiers |= _MOD_MAP[part]
        elif part in _VK_MAP:
            vk = _VK_MAP[part]
        elif len(part) == 1 and part.isalnum():
            # 단일 문자/숫자 → VK 코드 (A=0x41, 0=0x30)
            vk = ord(part.upper())
        else:
            print(f"[HotkeyParser] 인식할 수 없는 키: '{part}'")

    return modifiers, vk


class _WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, callback, voice_callback):
        super().__init__()
        self._callback = callback
        self._voice_callback = voice_callback

    def nativeEventFilter(self, event_type, message):
        if event_type == QByteArray(b"windows_generic_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID:
                    self._callback()
                    return True, 0
                elif msg.wParam == VOICE_HOTKEY_ID:
                    self._voice_callback()
                    return True, 0
        return False, 0


class HotkeyListener(QObject):
    hotkey_pressed = Signal()
    voice_hotkey_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered = False
        self._voice_registered = False
        self._filter = None

    def start(self, hotkey_spotlight: str = "Ctrl+Space",
              hotkey_voice: str = "Alt+Space"):
        if self._filter is not None:
            return

        mod, vk = parse_hotkey_string(hotkey_spotlight)
        ok = ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, mod | MOD_NOREPEAT, vk
        )
        if ok:
            self._registered = True
        else:
            print(f"[HotkeyListener] {hotkey_spotlight} 등록 실패 (다른 프로그램이 사용 중일 수 있음)")

        mod_v, vk_v = parse_hotkey_string(hotkey_voice)
        voice_ok = ctypes.windll.user32.RegisterHotKey(
            None, VOICE_HOTKEY_ID, mod_v | MOD_NOREPEAT, vk_v
        )
        if voice_ok:
            self._voice_registered = True
        else:
            print(f"[HotkeyListener] {hotkey_voice} 등록 실패 (다른 프로그램이 사용 중일 수 있음)")

        if self._registered or self._voice_registered:
            self._filter = _WinEventFilter(self._on_hotkey, self._on_voice_hotkey)
            QApplication.instance().installNativeEventFilter(self._filter)

    def stop(self):
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False
        if self._voice_registered:
            ctypes.windll.user32.UnregisterHotKey(None, VOICE_HOTKEY_ID)
            self._voice_registered = False
        if self._filter:
            QApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None

    def restart(self, hotkey_spotlight: str, hotkey_voice: str):
        """기존 핫키 해제 후 새 핫키로 재등록."""
        self.stop()
        self.start(hotkey_spotlight, hotkey_voice)

    def _on_hotkey(self):
        self.hotkey_pressed.emit()

    def _on_voice_hotkey(self):
        self.voice_hotkey_pressed.emit()
