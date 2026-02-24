"""
Nexus Shell - 자연어로 제어하는 지능형 PC 인터페이스
"""

import sys
import argparse
from config import OPENAI_API_KEY, OLLAMA_ENABLED


def check_api_key():
    if not OPENAI_API_KEY or OPENAI_API_KEY == "여기에_본인_API_키_입력":
        if OLLAMA_ENABLED:
            print("⚠️  OpenAI API 키 미설정 → Ollama 로컬 모드로 동작합니다.")
            print("   (폴백 비활성: 로컬 처리 실패 시 응답 불가)")
        else:
            print("❌ OpenAI API 키가 설정되지 않았습니다.")
            print("   .env 파일에 OPENAI_API_KEY를 입력해주세요.")
            print()
            print("   예시:")
            print("   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx")
            sys.exit(1)


def run_cli():
    """기존 CLI 모드"""
    from core.brain_router import BrainRouter
    from core.executor import Executor

    print()
    print("╔══════════════════════════════════════╗")
    print("║          ⚡ NEXUS SHELL ⚡           ║")
    print("║   자연어로 제어하는 PC 인터페이스    ║")
    print("╚══════════════════════════════════════╝")
    print()
    print("  명령 예시:")
    print("  • 크롬 켜줘")
    print("  • 엔비디아 주가 검색해줘")
    print("  • 유튜브 열어")
    print("  • CPU 몇 퍼센트야?")
    print("  • 배터리 얼마 남았어?")
    print()
    print("  종료: 'quit' 또는 '종료' 입력")
    print("  ─────────────────────────────────────")
    print()

    brain = BrainRouter()
    executor = Executor()

    while True:
        try:
            user_input = input("🔮 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Nexus Shell을 종료합니다.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "종료", "끝"):
            print("👋 Nexus Shell을 종료합니다.")
            break

        print("🧠 해석 중...", end="", flush=True)
        command = brain.interpret(user_input)

        if command is None:
            print("\r❌ 명령을 이해하지 못했습니다. 다시 말씀해주세요.")
            continue

        func_name = command["function"]
        args = command["arguments"]
        print(f"\r🎯 [{func_name}] {args}")

        result = executor.execute(command)
        print(f"{result}")
        print()


def run_gui():
    """GUI 모드 (Spotlight + 시스템 트레이)"""
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "NexusShell_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        sys.exit(0)

    from ui.app import NexusApp

    app = NexusApp()
    sys.exit(app.run())


def main():
    parser = argparse.ArgumentParser(description="Nexus Shell")
    parser.add_argument(
        "--cli", action="store_true", help="CLI 모드로 실행 (기본: GUI)"
    )
    args = parser.parse_args()

    check_api_key()

    if args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
