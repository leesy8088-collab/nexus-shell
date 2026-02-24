"""
VoiceWorker: 녹음 + STT 처리 (QThread)
sounddevice InputStream으로 오디오 수집 후 STTEngine으로 텍스트 변환
침묵 감지로 자동 녹음 종료
"""

import time
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from config import STT_SAMPLE_RATE
from core.stt import STTEngine

MIN_RECORDING_SECONDS = 0.5
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.2
SPEECH_MIN_DURATION = 0.3


class VoiceWorker(QThread):
    transcription_ready = Signal(str)
    error_occurred = Signal(str)
    recording_started = Signal()
    recording_stopped = Signal()
    level_updated = Signal(float)  # 0.0 ~ 1.0 음량 레벨

    def __init__(self, stt_engine: STTEngine, parent=None):
        super().__init__(parent)
        self._stt_engine = stt_engine
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._cancelled = False
        self._stopped = False
        self._speech_detected = False
        self._silence_start: float | None = None

    def run(self):
        try:
            self._chunks.clear()
            self._speech_detected = False
            self._silence_start = None

            self._stream = sd.InputStream(
                samplerate=STT_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self.recording_started.emit()

            while not self._stopped and not self._cancelled:
                self.msleep(50)

            self._stream.stop()
            self._stream.close()
            self._stream = None

            if self._cancelled:
                return

            self.recording_stopped.emit()

            if not self._chunks:
                self.error_occurred.emit("녹음된 오디오가 없습니다.")
                return

            audio = np.concatenate(self._chunks, axis=0).flatten()
            duration = len(audio) / STT_SAMPLE_RATE
            print(f"[Voice] 녹음 길이: {duration:.1f}초")

            if duration < MIN_RECORDING_SECONDS:
                self.error_occurred.emit("녹음이 너무 짧습니다 (0.5초 이상 필요).")
                return

            t0 = time.monotonic()
            text = self._stt_engine.transcribe(audio)
            print(f"[Voice] STT 소요: {time.monotonic()-t0:.1f}초 → \"{text}\"")
            if text:
                self.transcription_ready.emit(text)
            else:
                self.error_occurred.emit("음성을 인식하지 못했습니다.")

        except Exception as e:
            self.error_occurred.emit(f"음성 처리 오류: {e}")

    def _audio_callback(self, indata, frames, time_info, status):
        self._chunks.append(indata.copy())

        energy = np.sqrt(np.mean(indata ** 2))
        level = min(energy / 0.05, 1.0)  # 0.05 기준으로 정규화
        self.level_updated.emit(level)
        now = time.monotonic()

        if energy > SILENCE_THRESHOLD:
            self._speech_detected = True
            self._silence_start = None
        elif self._speech_detected:
            if self._silence_start is None:
                self._silence_start = now
            elif now - self._silence_start >= SILENCE_DURATION:
                self._stopped = True

    def stop_recording(self):
        """녹음 중지 → STT 처리 진행"""
        self._stopped = True

    def cancel(self):
        """녹음 취소 (STT 스킵)"""
        self._cancelled = True
        self._stopped = True
