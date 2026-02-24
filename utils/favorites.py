"""
FavoritesManager: 즐겨찾기(앱 + URL) 통합 관리
"""

import json
import os
import shutil
import subprocess
import urllib.request

from config import FAVORITES_PATH, ICONS_DIR, SITE_ALIASES


class FavoritesManager:
    def __init__(self):
        self._items: list[dict] = []
        self._ensure_icons_dir()
        self._load()

    # ── CRUD ──

    def add(self, name: str, fav_type: str, target: str, icon: str | None = None) -> dict:
        """즐겨찾기 추가. 이미 같은 이름이 있으면 덮어쓴다."""
        self.remove(name)
        item = {"name": name, "type": fav_type, "target": target, "icon": icon}
        self._items.append(item)
        self._save()
        return item

    def remove(self, name: str):
        """이름으로 즐겨찾기 삭제."""
        self._items = [it for it in self._items if it["name"] != name]
        self._save()

    def get_all(self) -> list[dict]:
        return list(self._items)

    def reload(self):
        """디스크에서 다시 읽기 (외부 변경 반영)."""
        self._load()

    # ── 별칭 동기화 ──

    def load_urls_into_aliases(self):
        """URL 타입 즐겨찾기 → SITE_ALIASES에 등록."""
        for item in self._items:
            if item["type"] == "url":
                key = item["name"].lower()
                if key not in SITE_ALIASES:
                    SITE_ALIASES[key] = item["target"]

    # ── 아이콘 자동 가져오기 (동기) ──

    def fetch_icon(self, item: dict) -> str | None:
        """아이콘을 가져와 캐시에 저장. 성공 시 경로 반환."""
        try:
            if item["type"] == "url":
                path = self._fetch_favicon(item)
            else:
                path = self._extract_exe_icon(item)
            if path:
                # self._items 내 실제 항목을 찾아서 업데이트
                for stored in self._items:
                    if stored["name"] == item["name"]:
                        stored["icon"] = path
                        break
                self._save()
            return path
        except Exception:
            return None

    def _fetch_favicon(self, item: dict) -> str | None:
        """Google Favicon API로 파비콘 다운로드."""
        try:
            target = item["target"]
            # URL에서 도메인 추출
            if "://" in target:
                domain = target.split("://", 1)[1].split("/", 1)[0]
            else:
                domain = target.split("/", 1)[0]

            safe_name = self._safe_filename(item["name"])
            save_path = os.path.join(ICONS_DIR, f"{safe_name}.png")

            url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                if len(data) < 100:
                    return None
                with open(save_path, "wb") as f:
                    f.write(data)
            return save_path
        except Exception:
            return None

    def _extract_exe_icon(self, item: dict) -> str | None:
        """PowerShell로 exe 아이콘 추출."""
        try:
            target = item["target"]
            # 경로 해석
            exe_path = shutil.which(target) or target
            if not os.path.isfile(exe_path):
                return None

            safe_name = self._safe_filename(item["name"])
            save_path = os.path.join(ICONS_DIR, f"{safe_name}.png")

            ps_script = (
                f'Add-Type -AssemblyName System.Drawing; '
                f'$icon = [System.Drawing.Icon]::ExtractAssociatedIcon("{exe_path}"); '
                f'$icon.ToBitmap().Save("{save_path}")'
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0 and os.path.isfile(save_path):
                return save_path
            return None
        except Exception:
            return None

    # ── 내부 유틸 ──

    @staticmethod
    def _safe_filename(name: str) -> str:
        """파일명에 안전한 문자열로 변환."""
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)

    def _load(self):
        if os.path.isfile(FAVORITES_PATH):
            try:
                with open(FAVORITES_PATH, "r", encoding="utf-8") as f:
                    self._items = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._items = []
        else:
            self._items = []

    def _save(self):
        try:
            with open(FAVORITES_PATH, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def _ensure_icons_dir(self):
        os.makedirs(ICONS_DIR, exist_ok=True)
