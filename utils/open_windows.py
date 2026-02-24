"""
open_windows: 열린 창 목록 조회 및 포커스 전환 유틸리티
"""

import ctypes
import ctypes.wintypes
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Windows 상수
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GW_OWNER = 4

# 자기 자신의 PID
_OWN_PID = os.getpid()

# 시스템 창으로 무시할 클래스명
_IGNORED_CLASSES = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Progman", "WorkerW", "Button",
    "Windows.UI.Core.CoreWindow",
}


def _get_process_name(pid: int) -> str:
    """PID로부터 프로세스 실행 파일명 반환."""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = ctypes.wintypes.DWORD(512)
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        if ok:
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def get_open_windows() -> list[dict]:
    """
    열린 창 목록 반환.
    각 항목: {"hwnd": int, "title": str, "process_name": str}
    """
    results: list[dict] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        hwnd = int(hwnd)
        # 보이지 않는 창 제외
        if not user32.IsWindowVisible(hwnd):
            return True
        # 제목 없는 창 제외
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        # 소유자가 있는 창 제외 (팝업/다이얼로그)
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        # 클래스명 확인 → 시스템 창 제외
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if class_buf.value in _IGNORED_CLASSES:
            return True
        # 자기 자신 제외
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == _OWN_PID:
            return True
        # 제목 가져오기
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value.strip()
        if not title:
            return True
        # 프로세스명
        process_name = _get_process_name(pid.value)

        results.append({
            "hwnd": hwnd,
            "title": title,
            "process_name": process_name,
        })
        return True

    user32.EnumWindows(callback, 0)
    return results


# 브라우저 프로세스 판별
_BROWSER_EXES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "whale.exe"}


def get_browser_tabs() -> list[dict]:
    """
    UIAutomation을 사용해 브라우저 탭 목록 추출 시도.
    실패 시 빈 리스트 반환 (graceful fallback).
    각 항목: {"hwnd": int, "title": str, "process_name": str, "is_tab": True}
    """
    try:
        import uiautomation as auto
    except ImportError:
        return []

    tabs: list[dict] = []
    try:
        windows = get_open_windows()
        for win in windows:
            if win["process_name"].lower() not in _BROWSER_EXES:
                continue
            hwnd = win["hwnd"]
            try:
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl is None:
                    continue
                # 탭 컨트롤 찾기
                tab_ctrl = ctrl.TabControl(searchDepth=5)
                if tab_ctrl is None:
                    continue
                tab_items = tab_ctrl.GetChildren()
                for tab_item in tab_items:
                    name = tab_item.Name
                    if name and name.strip():
                        tabs.append({
                            "hwnd": hwnd,
                            "title": name.strip(),
                            "process_name": win["process_name"],
                            "is_tab": True,
                        })
            except Exception:
                continue
    except Exception:
        pass
    return tabs


def focus_window(hwnd: int):
    """지정한 창을 포그라운드로 전환."""
    # 최소화 상태면 복원
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
