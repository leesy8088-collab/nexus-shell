"""
ShortcutManager: 키워드 단축키 JSON 로드/저장/매칭
"""

import json
import os
from config import SHORTCUTS_PATH


class ShortcutManager:
    def __init__(self):
        self._shortcuts: dict[str, list[dict]] = {}
        self._load()

    def match(self, text: str) -> list[dict] | None:
        """키워드 정확 매칭. 매칭되면 명령 리스트, 아니면 None."""
        return self._shortcuts.get(text.strip())

    def get_all(self) -> dict[str, list[dict]]:
        """전체 단축키 반환 (설정 창 표시용)."""
        return dict(self._shortcuts)

    def add(self, keyword: str, commands: list[dict]):
        """단축키 추가 + 저장."""
        self._shortcuts[keyword] = commands
        self._save()

    def remove(self, keyword: str):
        """단축키 삭제 + 저장."""
        self._shortcuts.pop(keyword, None)
        self._save()

    def reload(self):
        """외부에서 변경된 설정 다시 로드."""
        self._load()

    def _load(self):
        if os.path.exists(SHORTCUTS_PATH):
            try:
                with open(SHORTCUTS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._shortcuts = data.get("shortcuts", {})
            except (json.JSONDecodeError, IOError):
                self._shortcuts = {}
        else:
            self._shortcuts = {}
            self._save()

    def _save(self):
        data = {"shortcuts": self._shortcuts}
        with open(SHORTCUTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
