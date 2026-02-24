"""
ClipboardHistoryManager: 클립보드 히스토리 관리. JSON 메타 + 파일 저장.
"""

import json
import os
import time
import uuid

from config import (
    CLIPBOARD_HISTORY_PATH, CLIPBOARD_DATA_DIR,
    CLIPBOARD_MAX_ITEMS, CLIPBOARD_MAX_BYTES, CLIPBOARD_MAX_IMAGE_BYTES,
)


class ClipboardHistoryManager:
    """클립보드 히스토리 관리. JSON 메타 + 파일 저장."""

    def __init__(self):
        self._items: list[dict] = []
        os.makedirs(CLIPBOARD_DATA_DIR, exist_ok=True)
        self._load()

    # ── 추가 ──

    def add_text(self, text: str) -> dict | None:
        """텍스트 클립보드 항목 추가. 1MB 초과 시 None."""
        raw = text.encode("utf-8")
        if len(raw) > CLIPBOARD_MAX_BYTES:
            return None
        # 중복 방지: 직전 항목과 동일하면 스킵
        if self._items and self._items[0].get("type") == "text":
            prev_path = self._items[0].get("data_path", "")
            if os.path.isfile(prev_path):
                with open(prev_path, "r", encoding="utf-8") as f:
                    if f.read() == text:
                        return None
        item = self._create_item("text", text[:200], text)
        return item

    def add_image(self, image_bytes: bytes) -> dict | None:
        """이미지(PNG bytes) 클립보드 항목 추가. 5MB 초과 시 None."""
        if len(image_bytes) > CLIPBOARD_MAX_IMAGE_BYTES:
            return None
        if self._items and self._items[0].get("type") == "image":
            prev_path = self._items[0].get("data_path", "")
            if os.path.isfile(prev_path):
                with open(prev_path, "rb") as f:
                    if f.read() == image_bytes:
                        return None
        item = self._create_item("image", "[이미지]", image_bytes)
        return item

    def _create_item(self, item_type, preview, data) -> dict:
        """항목 생성, 파일 저장, 리스트 앞에 삽입, 초과분 삭제."""
        item_id = uuid.uuid4().hex[:8]
        ext = ".txt" if item_type == "text" else ".png"
        data_path = os.path.join(CLIPBOARD_DATA_DIR, f"{item_id}{ext}")
        mode = "w" if item_type == "text" else "wb"
        encoding = "utf-8" if item_type == "text" else None
        with open(data_path, mode, encoding=encoding) as f:
            f.write(data)
        item = {
            "id": item_id,
            "type": item_type,
            "preview": preview,
            "data_path": data_path,
            "timestamp": time.time(),
            "size_bytes": len(data) if isinstance(data, bytes) else len(data.encode("utf-8")),
        }
        self._items.insert(0, item)
        self._trim()
        self._save()
        return item

    def _trim(self):
        """CLIPBOARD_MAX_ITEMS 초과분 삭제 (파일 포함)."""
        while len(self._items) > CLIPBOARD_MAX_ITEMS:
            old = self._items.pop()
            if os.path.isfile(old.get("data_path", "")):
                os.remove(old["data_path"])

    # ── 조회 ──

    def get_all(self) -> list[dict]:
        return list(self._items)

    # ── 삭제 ──

    def remove(self, item_id: str):
        for it in self._items:
            if it["id"] == item_id:
                if os.path.isfile(it.get("data_path", "")):
                    os.remove(it["data_path"])
                self._items.remove(it)
                break
        self._save()

    def clear(self):
        for it in self._items:
            if os.path.isfile(it.get("data_path", "")):
                os.remove(it["data_path"])
        self._items.clear()
        self._save()

    # ── 데이터 읽기 (재복사용) ──

    def get_data(self, item_id: str) -> tuple[str, bytes | str | None]:
        """(type, data) 반환. 텍스트면 str, 이미지면 bytes."""
        for it in self._items:
            if it["id"] == item_id:
                path = it.get("data_path", "")
                if not os.path.isfile(path):
                    return it["type"], None
                if it["type"] == "text":
                    with open(path, "r", encoding="utf-8") as f:
                        return "text", f.read()
                else:
                    with open(path, "rb") as f:
                        return "image", f.read()
        return "text", None

    # ── 직렬화 ──

    def _load(self):
        if os.path.isfile(CLIPBOARD_HISTORY_PATH):
            try:
                with open(CLIPBOARD_HISTORY_PATH, "r", encoding="utf-8") as f:
                    self._items = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._items = []
        else:
            self._items = []

    def _save(self):
        try:
            with open(CLIPBOARD_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
