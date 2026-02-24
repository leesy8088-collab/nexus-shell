@echo off
chcp 65001 >nul
echo ══════════════════════════════════════
echo   Nexus Shell — Build
echo ══════════════════════════════════════
echo.

:: PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] PyInstaller 설치 중...
    pip install pyinstaller
    echo.
)

:: 빌드
echo [2/3] 빌드 중... (수 분 소요)
pyinstaller nexus_shell.spec --noconfirm
echo.

if not exist "dist\NexusShell\NexusShell.exe" (
    echo ❌ 빌드 실패. 위 에러 메시지를 확인하세요.
    pause
    exit /b 1
)

:: 사용자 데이터 템플릿 복사
echo [3/3] 기본 설정 파일 복사 중...
if not exist "dist\NexusShell\settings.json" (
    echo {"shortcuts": {}} > "dist\NexusShell\settings.json"
)

echo.
echo ══════════════════════════════════════
echo   ✅ 빌드 완료!
echo   결과: dist\NexusShell\
echo.
echo   배포 방법:
echo   1. dist\NexusShell 폴더를 통째로 zip
echo   2. 받는 사람은 압축 풀고 NexusShell.exe 실행
echo.
echo   필요 조건 (받는 사람 PC):
echo   - Windows 10/11
echo   - Ollama 설치 + 모델 다운: ollama pull qwen2.5:3b
echo ══════════════════════════════════════
pause
