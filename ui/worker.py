"""
BrainWorker: QThread로 LLM 호출 (UI 프리징 방지)
"""

from PySide6.QtCore import QThread, Signal


class BrainWorker(QThread):
    result_ready = Signal(str, str)   # (func_name, result_text)
    error_occurred = Signal(str)      # error_msg

    def __init__(self, brain, executor, user_input, parent=None):
        super().__init__(parent)
        self._brain = brain
        self._executor = executor
        self._user_input = user_input

    def run(self):
        try:
            command = self._brain.interpret(self._user_input)

            if command is None:
                self.error_occurred.emit("명령을 이해하지 못했습니다.")
                return

            func_name = command["function"]
            result = self._executor.execute(command)
            self.result_ready.emit(func_name, result)

        except Exception as e:
            self.error_occurred.emit(str(e))
