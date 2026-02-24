"""
LocalBrain: Ollama 로컬 LLM을 사용한 명령 분류기.
JSON 프롬프팅 + few-shot 방식으로 사용자 입력을 분류한다.
"""

import json
import re
import urllib.request
import urllib.error
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

LOCAL_SYSTEM_PROMPT = """You are Nexus Shell, a PC control assistant.
Classify user input into exactly ONE JSON command. Output ONLY valid JSON, no extra text.

Available functions:
1. run_app: Launch an application. Args: {"app_name": "<name>"}
2. open_url: Open website or search. Args: {"url": "...", "search_query": "...", "site_name": "..."}
3. check_system: System info. Args: {"info_type": "cpu"|"memory"|"disk"|"battery"|"network"|"all"}
4. general_response: General chat. Args: {"message": "<response>"}

Rules:
- Output ONLY a single JSON object: {"function": "...", "arguments": {...}}
- For search_query, use the user's EXACT words. Never translate or rephrase.
- For site-specific search, include both site_name and search_query.
- Respond in Korean for general_response messages."""

# few-shot 예시 (대화 히스토리 형태)
FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "크롬 켜줘"},
    {"role": "assistant", "content": '{"function": "run_app", "arguments": {"app_name": "크롬"}}'},
    {"role": "user", "content": "유튜브에서 고양이 검색해줘"},
    {"role": "assistant", "content": '{"function": "open_url", "arguments": {"site_name": "유튜브", "search_query": "고양이"}}'},
    {"role": "user", "content": "CPU 사용량 알려줘"},
    {"role": "assistant", "content": '{"function": "check_system", "arguments": {"info_type": "cpu"}}'},
    {"role": "user", "content": "네이버 열어"},
    {"role": "assistant", "content": '{"function": "open_url", "arguments": {"site_name": "네이버"}}'},
    {"role": "user", "content": "오늘 기분이 좋아"},
    {"role": "assistant", "content": '{"function": "general_response", "arguments": {"message": "좋은 하루 보내고 계시군요! 무엇을 도와드릴까요?"}}'},
]

VALID_FUNCTIONS = {"run_app", "open_url", "check_system", "general_response"}


class LocalBrain:
    """Ollama 로컬 LLM을 통한 명령 분류기."""

    def __init__(self):
        self._api_url = f"{OLLAMA_BASE_URL}/api/chat"

    def interpret(self, user_input: str) -> dict | None:
        """
        사용자 입력을 로컬 LLM으로 해석.
        성공 시 {"function": ..., "arguments": {...}} 반환, 실패 시 None.
        """
        messages = [
            {"role": "system", "content": LOCAL_SYSTEM_PROMPT},
            *FEW_SHOT_EXAMPLES,
            {"role": "user", "content": user_input},
        ]

        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.1,
                "num_predict": 150,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            self._api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"[LocalBrain] Ollama 통신 실패: {e}")
            raise  # 라우터에서 폴백 처리

        raw = body.get("message", {}).get("content", "").strip()
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> dict | None:
        """2단계 파싱: json.loads → 정규식 추출."""
        # 1차: 직접 파싱
        try:
            parsed = json.loads(raw)
            if self._is_valid_command(parsed):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # 2차: 정규식으로 JSON 객체 추출
        match = re.search(r"\{[^{}]*\{[^{}]*\}[^{}]*\}", raw)
        if not match:
            match = re.search(r"\{[^{}]+\}", raw)
        if match:
            try:
                parsed = json.loads(match.group())
                if self._is_valid_command(parsed):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

        print(f"[LocalBrain] 파싱 실패: {raw[:100]}")
        return None

    @staticmethod
    def _is_valid_command(parsed: dict) -> bool:
        """function 화이트리스트 + arguments dict 검증."""
        if not isinstance(parsed, dict):
            return False
        func = parsed.get("function")
        args = parsed.get("arguments")
        return func in VALID_FUNCTIONS and isinstance(args, dict)
