import subprocess
import shutil
import webbrowser
import urllib.parse
import ctypes
import time
from config import APP_ALIASES, SITE_ALIASES, SITE_SEARCH

# cmd /c start 래퍼 전용 (래퍼 콘솔만 숨김)
_SI_HIDE = subprocess.STARTUPINFO()
_SI_HIDE.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_SI_HIDE.wShowWindow = 0  # SW_HIDE

from utils.system_info import get_system_info


class Executor:
    """해석된 명령을 실제로 시스템에서 실행"""
    
    def run_app(self, app_name: str) -> str:
        """앱을 실행합니다."""
        app_key = app_name.lower().strip()
        executable = APP_ALIASES.get(app_key, app_key)

        try:
            # .cmd/.bat 래퍼(예: VS Code의 "code")는 콘솔 숨김 실행
            # → 중간 CMD 창이 뜨는 것을 방지
            resolved = shutil.which(executable)
            if resolved and resolved.lower().endswith(('.cmd', '.bat')):
                subprocess.Popen(
                    ['cmd', '/c', resolved],
                    startupinfo=_SI_HIDE,
                )
                return f"✅ '{app_name}' 실행 완료"

            # 일반 앱은 ShellExecuteW — 래퍼 프로세스 없이 새 창 1개만 생성
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "open", executable, None, None, 1  # SW_SHOWNORMAL
            )
            if ret > 32:
                return f"✅ '{app_name}' 실행 완료"
            else:
                return f"❌ '{app_name}'을(를) 찾을 수 없습니다. config.py의 APP_ALIASES에 경로를 추가해보세요."
        except Exception as e:
            return f"❌ '{app_name}' 실행 중 오류: {e}"
    
    def open_url(self, url: str = "", search_query: str = "", site_name: str = "") -> str:
        """URL을 열거나 웹 검색을 수행합니다."""
        try:
            # 1. 직접 URL이 있으면 그대로 열기
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                webbrowser.open(url)
                return f"✅ {url} 열기 완료"
            
            # 2. 사이트 별칭 처리
            if site_name:
                site_key = site_name.lower().strip()
                site_url = SITE_ALIASES.get(site_key)

                # 사이트 + 검색어 → 사이트 내 검색
                if site_url and search_query:
                    encoded = urllib.parse.quote(search_query)
                    search_url = SITE_SEARCH.get(site_key)
                    if search_url:
                        full_url = search_url.format(query=encoded)
                    else:
                        # 사이트 내 검색 패턴이 없으면 구글 site: 검색
                        domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")
                        full_url = f"https://www.google.com/search?q=site:{domain}+{encoded}"
                    webbrowser.open(full_url)
                    return f"✅ {site_name}에서 '{search_query}' 검색 완료"

                # 사이트만 열기
                if site_url:
                    webbrowser.open(site_url)
                    return f"✅ {site_name} ({site_url}) 열기 완료"

                # 별칭에 없으면 검색으로 처리
                search_query = site_name

            # 3. 검색어가 있으면 구글 검색
            if search_query:
                encoded = urllib.parse.quote(search_query)
                search_url = f"https://www.google.com/search?q={encoded}"
                webbrowser.open(search_url)
                return f"✅ '{search_query}' 검색 완료"
            
            return "❌ URL이나 검색어를 인식하지 못했습니다."
            
        except Exception as e:
            return f"❌ 웹 열기 중 오류: {e}"
    
    def check_system(self, info_type: str) -> str:
        """시스템 정보를 조회합니다."""
        return get_system_info(info_type)
    
    @staticmethod
    def _get_visible_windows() -> set[int]:
        """현재 보이는 모든 윈도우 핸들 집합 반환."""
        user32 = ctypes.windll.user32
        result = set()

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                result.add(int(hwnd))
            return True

        user32.EnumWindows(callback, 0)
        return result

    @staticmethod
    def _get_work_area():
        """작업 표시줄 제외한 화면 영역 반환 (x, y, w, h)."""
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top

    @staticmethod
    def _get_frame_margins(hwnd):
        """DWM 보이지 않는 그림자 테두리 크기 반환 (left, right, bottom)."""
        from ctypes import wintypes
        try:
            rect_win = wintypes.RECT()
            rect_frame = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect_win))
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, 9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                ctypes.byref(rect_frame), ctypes.sizeof(rect_frame)
            )
            return (
                rect_frame.left - rect_win.left,
                rect_win.right - rect_frame.right,
                rect_win.bottom - rect_frame.bottom,
            )
        except Exception:
            return 0, 0, 0

    def launch_and_snap(self, position: str,
                        app_name: str = "", site_name: str = "", url: str = "") -> str:
        """앱/사이트를 실행한 뒤 해당 창을 지정 위치에 배치합니다."""
        _labels = {"left": "왼쪽", "right": "오른쪽", "maximize": "최대화", "minimize": "최소화"}
        label = _labels.get(position.lower().strip())
        if not label:
            return f"❌ 알 수 없는 위치: {position}"

        try:
            user32 = ctypes.windll.user32

            # 1) 실행 전 윈도우 스냅샷
            windows_before = self._get_visible_windows()

            # 2) 앱 또는 사이트 실행
            if app_name:
                result = self.run_app(app_name)
            elif site_name or url:
                result = self.open_url(site_name=site_name, url=url)
            else:
                return "❌ 실행할 대상이 없습니다."

            if result.startswith("❌"):
                return result

            # 3) 새로 생긴 창 찾기 (최대 ~5초)
            hwnd_new = None
            for _ in range(35):
                time.sleep(0.15)
                windows_now = self._get_visible_windows()
                new_windows = windows_now - windows_before
                if new_windows:
                    hwnd_new = max(new_windows)
                    break

            if not hwnd_new:
                return f"{result} (⚠️ 창 배치 실패 — 새 창을 찾지 못함)"

            # 4) 창을 직접 좌표로 이동 (키보드 시뮬레이션 X)
            wx, wy, ww, wh = self._get_work_area()

            # SW_RESTORE(9) — 최소화/최대화 해제 후 이동 가능하게
            user32.ShowWindow(hwnd_new, 9)
            time.sleep(0.05)

            # 보이지 않는 그림자 테두리 보정 (Windows 10/11)
            bl, br, bb = self._get_frame_margins(hwnd_new)

            pos = position.lower().strip()
            if pos == "left":
                user32.MoveWindow(hwnd_new, wx - bl, wy, ww // 2 + bl + br, wh + bb, True)
            elif pos == "right":
                user32.MoveWindow(hwnd_new, wx + ww // 2 - bl, wy, ww // 2 + bl + br, wh + bb, True)
            elif pos == "maximize":
                user32.ShowWindow(hwnd_new, 3)  # SW_MAXIMIZE
            elif pos == "minimize":
                user32.ShowWindow(hwnd_new, 6)  # SW_MINIMIZE

            name = app_name or site_name or url
            return f"✅ '{name}' {label} 배치 완료"

        except Exception as e:
            return f"❌ 배치 중 오류: {e}"

    def general_response(self, message: str) -> str:
        """일반 대화 응답을 반환합니다."""
        return f"💬 {message}"
    
    def execute(self, command: dict) -> str:
        """
        Brain이 해석한 명령을 실행합니다.
        
        Args:
            command: {"function": "함수명", "arguments": {파라미터들}}
        
        Returns:
            실행 결과 문자열
        """
        func_name = command["function"]
        args = command["arguments"]
        
        # 화이트리스트 기반 실행 (보안)
        handlers = {
            "run_app": self.run_app,
            "open_url": self.open_url,
            "launch_and_snap": self.launch_and_snap,
            "check_system": self.check_system,
            "general_response": self.general_response,
        }
        
        handler = handlers.get(func_name)
        if handler:
            return handler(**args)
        else:
            return f"❌ 알 수 없는 명령: {func_name}"
