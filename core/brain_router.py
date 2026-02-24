"""
BrainRouter: 로컬 Ollama → OpenAI 폴백 하이브리드 라우터.
interpret() 인터페이스는 Brain과 동일.
"""

import json
import urllib.request
import urllib.error
from config import OLLAMA_ENABLED, OLLAMA_BASE_URL, OLLAMA_MODEL
from core.local_brain import LocalBrain
from core.brain import Brain


class BrainRouter:
    """로컬 LLM 우선, 실패 시 OpenAI API 폴백."""

    def __init__(self):
        self._ollama_available = False
        self._local_brain = None
        self._cloud_brain = Brain()

        if OLLAMA_ENABLED:
            self._ollama_available = self._check_ollama()
            if self._ollama_available:
                self._local_brain = LocalBrain()

    def _check_ollama(self) -> bool:
        """Ollama 서버 실행 여부 + 모델 존재 확인."""
        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            models = [m.get("name", "") for m in data.get("models", [])]
            # "qwen2.5:3b" 또는 "qwen2.5:3b-..." 형태 매칭
            found = any(m == OLLAMA_MODEL or m.startswith(f"{OLLAMA_MODEL}-")
                        for m in models)
            if found:
                print(f"[BrainRouter] Ollama 연결 성공 (모델: {OLLAMA_MODEL})")
                return True
            else:
                print(f"[BrainRouter] Ollama 서버 실행 중이나 모델 '{OLLAMA_MODEL}' 미설치")
                print(f"  → 설치: ollama pull {OLLAMA_MODEL}")
                return False
        except (urllib.error.URLError, TimeoutError, OSError):
            print("[BrainRouter] Ollama 서버 미실행 → OpenAI API만 사용")
            return False

    def interpret(self, user_input: str) -> dict | None:
        """로컬 LLM 시도 → 실패 시 OpenAI 폴백."""
        # 로컬 시도
        if self._ollama_available and self._local_brain:
            try:
                result = self._local_brain.interpret(user_input)
                if result is not None:
                    print(f"[BrainRouter] 로컬 LLM 처리 완료: {result['function']}")
                    return result
                print("[BrainRouter] 로컬 파싱 실패 → OpenAI 폴백")
            except (urllib.error.URLError, TimeoutError, OSError):
                print("[BrainRouter] Ollama 연결 오류 → 이후 호출은 OpenAI만 사용")
                self._ollama_available = False
            except Exception as e:
                print(f"[BrainRouter] 로컬 처리 예외: {e} → OpenAI 폴백")

        # OpenAI 폴백
        return self._cloud_brain.interpret(user_input)

    def clear_history(self):
        """대화 기록 초기화."""
        self._cloud_brain.clear_history()
