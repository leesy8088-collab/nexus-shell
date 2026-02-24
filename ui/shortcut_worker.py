"""
ShortcutWorker: 복합 명령 순차 실행 Worker (QThread)
"""

from PySide6.QtCore import QThread, Signal


class ShortcutWorker(QThread):
    result_ready = Signal(str)     # 모든 결과를 합쳐서 반환
    error_occurred = Signal(str)   # 에러 메시지

    def __init__(self, executor, commands: list[dict], parent=None):
        super().__init__(parent)
        self._executor = executor
        self._commands = commands

    def run(self):
        try:
            results = []
            for cmd in self._commands:
                result = self._executor.execute(cmd)
                results.append(result)

            total = len(self._commands)
            summary = "\n".join(results)
            if total > 1:
                summary += f"\n\n⚡ {total}개 명령 실행 완료"
            self.result_ready.emit(summary)

        except Exception as e:
            self.error_occurred.emit(str(e))
