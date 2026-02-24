"""
GitHub Releases 기반 자동 업데이트 체커.
백그라운드 스레드로 실행되어 앱 시작을 지연시키지 않음.
"""

import json
import re
import urllib.request
import urllib.error
from typing import Optional

from version import __version__
from config import GITHUB_REPO


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' 또는 '1.2.3' → (1, 2, 3) 튜플로 변환."""
    cleaned = tag.lstrip("vV")
    parts = re.findall(r"\d+", cleaned)
    return tuple(int(p) for p in parts)


def check_for_update() -> Optional[tuple[str, str, str]]:
    """
    GitHub Releases에서 최신 버전 확인.

    Returns:
        새 버전이 있으면 (new_version, download_url, release_notes) 튜플.
        최신이거나 오류 시 None.
    """
    if not GITHUB_REPO or GITHUB_REPO == "owner/repo":
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NexusShell-Updater",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None

    tag_name = data.get("tag_name", "")
    if not tag_name:
        return None

    try:
        remote_ver = _parse_version(tag_name)
        local_ver = _parse_version(__version__)
    except (ValueError, IndexError):
        return None

    if remote_ver <= local_ver:
        return None

    # 다운로드 URL: .zip asset 우선, 없으면 release 페이지
    download_url = data.get("html_url", "")
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(".zip"):
            download_url = asset.get("browser_download_url", download_url)
            break

    release_notes = data.get("body", "") or ""

    return tag_name, download_url, release_notes
