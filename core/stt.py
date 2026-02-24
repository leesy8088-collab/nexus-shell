"""
STTEngine: faster-whisper 래퍼
"""

import threading
import numpy as np

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE


class STTEngine:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._hint_prompt = ""

    def set_hints(self, keywords: list[str]):
        """인식 힌트 키워드 설정 (단축키, 앱/사이트 별칭)"""
        self._hint_prompt = ", ".join(keywords)

    def preload(self):
        """백그라운드 스레드에서 모델 미리 로딩"""
        threading.Thread(target=self._ensure_model, daemon=True).start()

    def _ensure_model(self):
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )

    def transcribe(self, audio: np.ndarray) -> str:
        """float32 numpy 배열 → 텍스트 (Korean, VAD 필터 적용)"""
        self._ensure_model()
        segments, _ = self._model.transcribe(
            audio,
            language="ko",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
            hallucination_silence_threshold=0.5,
            no_speech_threshold=0.5,
        )
        text = "".join(seg.text for seg in segments).strip()
        text = text.strip(".,!?;:~… ")
        return text
