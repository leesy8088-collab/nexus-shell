"""
Start Menu .lnk 파일을 스캔하여 설치된 데스크톱 앱을 자동 발견·등록.
PowerShell(Windows 기본 내장)만 사용하므로 추가 의존성 없음.
"""

import json
import os
import subprocess
import tempfile
import time
import winreg

from config import APP_ALIASES, BASE_DIR

# ── 캐시 / 사용자 앱 경로 ──
_CACHE_PATH = os.path.join(BASE_DIR, "discovered_apps.json")
_CACHE_MAX_AGE = 7 * 24 * 3600  # 7일 (초)
_USER_APPS_PATH = os.path.join(BASE_DIR, "user_apps.json")

# 제외 키워드 (소문자 비교)
_EXCLUDE_KEYWORDS = (
    "uninstall", "제거", "updater", "update", "setup", "installer",
    "repair", "help", "도움말", "diagnostic", "configuration",
    "license", "readme", "release notes", "migration",
)

# PowerShell 스크립트: .lnk → (DisplayName\tTargetPath) 출력
# 배열은 명시적 변수 할당 후 @()로 묶어야 -File 모드에서 안정 동작
_PS_SCRIPT = """\
$shell = New-Object -ComObject WScript.Shell
$d1 = [Environment]::GetFolderPath('CommonStartMenu') + '\\Programs'
$d2 = [Environment]::GetFolderPath('StartMenu') + '\\Programs'
$dirs = @($d1, $d2)
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) { continue }
    Get-ChildItem -Path $dir -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $link = $shell.CreateShortcut($_.FullName)
            $target = $link.TargetPath
            if ($target -and $target.EndsWith('.exe')) {
                $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                Write-Output ("$name`t$target")
            }
        } catch {}
    }
}
"""

# subprocess 콘솔 숨김 플래그
_CREATE_NO_WINDOW = 0x0800_0000


def _scan_start_menu() -> dict[str, str]:
    """PowerShell로 Start Menu .lnk 파일을 스캔하여 {display_name: exe_path} 반환."""
    tmp = None
    try:
        # 임시 .ps1 파일에 스크립트 작성 (멀티라인 파싱 안정)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", encoding="utf-8", delete=False,
        )
        tmp.write(_PS_SCRIPT)
        tmp.close()

        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", tmp.name],
            capture_output=True, text=True, timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {}
    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    apps: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        name, path = parts[0].strip(), parts[1].strip()
        if not name or not path:
            continue

        # 제외 키워드 필터
        name_lower = name.lower()
        if any(kw in name_lower for kw in _EXCLUDE_KEYWORDS):
            continue

        # 실제 파일 존재 확인
        if not os.path.isfile(path):
            continue

        apps[name] = path
    return apps


def _load_cache() -> dict | None:
    """캐시 파일 로드. 유효하면 dict, 아니면 None."""
    try:
        if not os.path.isfile(_CACHE_PATH):
            return None
        age = time.time() - os.path.getmtime(_CACHE_PATH)
        if age > _CACHE_MAX_AGE:
            return None
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_cache(apps: dict[str, str]) -> None:
    """발견된 앱을 JSON 캐시로 저장."""
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _scan_registry() -> dict[str, str]:
    """레지스트리 Uninstall 키에서 설치된 앱 {display_name: exe_path} 반환."""
    _UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    apps: dict[str, str] = {}
    for hive, key_path in _UNINSTALL_KEYS:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                except OSError:
                    continue
                try:
                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except OSError:
                        continue
                    # InstallLocation 또는 DisplayIcon 에서 exe 경로 추출
                    exe_path = ""
                    for val_name in ("DisplayIcon", "InstallLocation"):
                        try:
                            val = winreg.QueryValueEx(subkey, val_name)[0]
                            if not val:
                                continue
                            # DisplayIcon: "C:\...\app.exe,0" 형태
                            candidate = val.split(",")[0].strip().strip('"')
                            if candidate.lower().endswith(".exe") and os.path.isfile(candidate):
                                exe_path = candidate
                                break
                            # InstallLocation: 폴더 내 exe 찾기
                            if os.path.isdir(candidate):
                                for f in os.listdir(candidate):
                                    if f.lower().endswith(".exe"):
                                        full = os.path.join(candidate, f)
                                        if os.path.isfile(full):
                                            exe_path = full
                                            break
                                if exe_path:
                                    break
                        except OSError:
                            continue
                    if not name or not exe_path:
                        continue
                    name = name.strip()
                    name_lower = name.lower()
                    if any(kw in name_lower for kw in _EXCLUDE_KEYWORDS):
                        continue
                    if name not in apps:
                        apps[name] = exe_path
                finally:
                    winreg.CloseKey(subkey)
        finally:
            winreg.CloseKey(key)
    return apps


def scan_installed_apps(force_refresh: bool = False) -> dict[str, str]:
    """설치 앱 스캔. 시작 메뉴 + 레지스트리 병합."""
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            return cached

    apps = _scan_start_menu()
    # 레지스트리에서 추가 발견 (시작 메뉴에 없는 앱)
    reg_apps = _scan_registry()
    existing_paths = {v.lower() for v in apps.values()}
    for name, path in reg_apps.items():
        if path.lower() not in existing_paths and name not in apps:
            apps[name] = path

    if apps:
        _save_cache(apps)
    return apps


def load_user_apps() -> int:
    """user_apps.json → APP_ALIASES 로드. 반환: 로드된 앱 수."""
    try:
        if not os.path.isfile(_USER_APPS_PATH):
            return 0
        with open(_USER_APPS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return 0
    except (json.JSONDecodeError, OSError):
        return 0

    added = 0
    for name, path in data.items():
        key = name.lower()
        if key not in APP_ALIASES:
            APP_ALIASES[key] = path
            added += 1
    return added


def _save_user_apps(apps: dict[str, str]) -> None:
    """user_apps.json에 저장."""
    try:
        with open(_USER_APPS_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_user_apps_raw() -> dict[str, str]:
    """user_apps.json 원본 로드."""
    try:
        if not os.path.isfile(_USER_APPS_PATH):
            return {}
        with open(_USER_APPS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def add_user_app(name: str, path: str) -> None:
    """앱 하나를 user_apps.json + APP_ALIASES에 추가."""
    apps = load_user_apps_raw()
    apps[name] = path
    _save_user_apps(apps)
    APP_ALIASES[name.lower()] = path


def remove_user_app(name: str) -> None:
    """앱 하나를 user_apps.json + APP_ALIASES에서 제거."""
    apps = load_user_apps_raw()
    # 원본 이름(대소문자 무시) 찾아 삭제
    to_del = [k for k in apps if k.lower() == name.lower()]
    for k in to_del:
        del apps[k]
    _save_user_apps(apps)
    APP_ALIASES.pop(name.lower(), None)


def get_discovered_apps() -> dict[str, str]:
    """스캔 결과에서 이미 등록된 앱을 제외한 후보 목록 반환."""
    discovered = scan_installed_apps()
    if not discovered:
        return {}

    existing_paths = {v.lower() for v in APP_ALIASES.values()}
    existing_keys = set(APP_ALIASES.keys())

    candidates: dict[str, str] = {}
    for display_name, exe_path in discovered.items():
        key = display_name.lower()
        if key in existing_keys:
            continue
        if exe_path.lower() in existing_paths:
            continue
        candidates[display_name] = exe_path
    return candidates
