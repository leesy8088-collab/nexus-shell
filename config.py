import os
import sys
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── 경로 설정 ──
# PyInstaller frozen 모드: exe 폴더 = 사용자 데이터, _MEIPASS = 번들 리소스
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

SHORTCUTS_PATH = os.path.join(BASE_DIR, "settings.json")
HISTORY_PATH = os.path.join(BASE_DIR, "history.json")
FAVORITES_PATH = os.path.join(BASE_DIR, "favorites.json")
PREFERENCES_PATH = os.path.join(BASE_DIR, "preferences.json")
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")

CLIPBOARD_HISTORY_PATH = os.path.join(BASE_DIR, "clipboard_history.json")
CLIPBOARD_DATA_DIR = os.path.join(BASE_DIR, "clipboard_data")
CLIPBOARD_MAX_ITEMS = 30
CLIPBOARD_MAX_BYTES = 1 * 1024 * 1024        # 텍스트 1MB
CLIPBOARD_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 이미지 5MB

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"

# ── Ollama 로컬 LLM 설정 ──
OLLAMA_ENABLED = True
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_TIMEOUT = 10

# ── GitHub 릴리즈 (자동 업데이트) ──
GITHUB_REPO = "leesy8088-collab/nexus-shell"

# ── UI 설정 ──
SPOTLIGHT_WIDTH = 600
SPOTLIGHT_INPUT_HEIGHT = 50
RESULT_AUTO_CLOSE_MS = 4000

# ── 음성 입력 (STT) 설정 ──
WHISPER_MODEL_SIZE = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
STT_SAMPLE_RATE = 16000

# 앱 별칭 → 실제 실행 경로 매핑 (Windows 기준)
# 사용자가 자유롭게 추가/수정 가능
APP_ALIASES = {
    # 브라우저
    "크롬": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "구글": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "엣지": "msedge",
    "edge": "msedge",
    
    # 기본 앱
    "메모장": "notepad",
    "notepad": "notepad",
    "계산기": "calc",
    "calculator": "calc",
    "탐색기": "explorer",
    "explorer": "explorer",
    "파일탐색기": "explorer",
    
    # 개발 도구
    "vscode": "code",
    "vs code": "code",
    "비주얼스튜디오코드": "code",
    
    # 미디어
    "그림판": "mspaint",
    "paint": "mspaint",
    
    # 시스템
    "cmd": "cmd",
    "터미널": "wt",
    "terminal": "wt",
    "powershell": "powershell",
    "설정": "ms-settings:",
    "작업관리자": "taskmgr",
}

# 사이트 내 검색 URL 패턴 ({query}에 검색어 삽입)
SITE_SEARCH = {
    "유튜브": "https://www.youtube.com/results?search_query={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "네이버": "https://search.naver.com/search.naver?query={query}",
    "naver": "https://search.naver.com/search.naver?query={query}",
    "구글": "https://www.google.com/search?q={query}",
    "google": "https://www.google.com/search?q={query}",
    "깃허브": "https://github.com/search?q={query}",
    "github": "https://github.com/search?q={query}",
}

# 웹사이트 별칭 → URL 매핑
SITE_ALIASES = {
    "유튜브": "https://www.youtube.com",
    "youtube": "https://www.youtube.com",
    "네이버": "https://www.naver.com",
    "naver": "https://www.naver.com",
    "구글": "https://www.google.com",
    "google": "https://www.google.com",
    "깃허브": "https://github.com",
    "github": "https://github.com",
    "챗지피티": "https://chat.openai.com",
    "chatgpt": "https://chat.openai.com",
}

# ── 개인화 설정 ──
DEFAULT_PREFS = {
    "hotkey_spotlight": "Ctrl+Space",
    "hotkey_voice": "Alt+Space",
    "spotlight_width": 600,
    "spotlight_position": 22,       # 화면 상단에서 %
    "spotlight_opacity": 230,       # 배경 alpha (0-255)
    "accent_color": "#6366f1",      # 테마 강조색
    "result_auto_close_ms": 4000,   # 결과 자동 닫힘 (ms)
    "auto_start": False,            # Windows 시작 시 자동 실행
}


def load_preferences() -> dict:
    """preferences.json 로드. 없으면 DEFAULT_PREFS 반환."""
    try:
        if os.path.isfile(PREFERENCES_PATH):
            with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 누락된 키는 기본값으로 채움
            merged = dict(DEFAULT_PREFS)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_PREFS)


def save_preferences(prefs: dict):
    """preferences.json 저장."""
    try:
        with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[preferences 저장 오류] {e}")
