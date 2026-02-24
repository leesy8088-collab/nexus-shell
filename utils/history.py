"""
명령 히스토리 관리: JSON 파일 기반 최근 입력 저장 + 방향키 순회.
"""

import json
import os

from config import HISTORY_PATH

_MAX_SIZE = 50


class HistoryManager:
    def __init__(self):
        self._commands: list[str] = []
        self._cursor: int = -1      # -1 = 현재 입력, 0 = 최신
        self._draft: str = ""       # 히스토리 진입 전 입력 중이던 텍스트
        self._load()

    def add(self, text: str):
        """명령 추가. 중복 시 기존 위치에서 제거 후 최신으로."""
        if text in self._commands:
            self._commands.remove(text)
        self._commands.insert(0, text)
        self._commands = self._commands[:_MAX_SIZE]
        self._save()
        self.reset_cursor()

    def previous(self, current_text: str) -> str | None:
        """위 방향키: 이전(오래된) 명령. 처음 진입 시 현재 입력을 draft로 저장."""
        if not self._commands:
            return None
        if self._cursor == -1:
            self._draft = current_text
        next_idx = self._cursor + 1
        if next_idx >= len(self._commands):
            return None
        self._cursor = next_idx
        return self._commands[self._cursor]

    def next(self) -> str | None:
        """아래 방향키: 다음(최신) 명령 또는 draft 복원."""
        if self._cursor <= -1:
            return None
        self._cursor -= 1
        if self._cursor == -1:
            return self._draft
        return self._commands[self._cursor]

    def reset_cursor(self):
        self._cursor = -1
        self._draft = ""

    def _load(self):
        try:
            if not os.path.isfile(HISTORY_PATH):
                return
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cmds = data.get("commands", [])
                if isinstance(cmds, list):
                    self._commands = [c for c in cmds if isinstance(c, str)]
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump({"commands": self._commands}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
