# ⚡ Nexus Shell

자연어와 음성으로 제어하는 지능형 PC 인터페이스

## 🚀 시작하기

### 1. 패키지 설치

```bash
cd nexus_shell
pip install -r requirements.txt
```

### 2. API 키 설정

`.env` 파일을 열어 본인의 OpenAI API 키를 입력하세요:

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. 실행

```bash
python main.py
```

## 💡 사용 예시

```
🔮 > 크롬 켜줘
🎯 [run_app] {'app_name': '크롬'}
✅ '크롬' 실행 완료

🔮 > 엔비디아 주가 검색해줘
🎯 [open_url] {'search_query': '엔비디아 주가'}
✅ '엔비디아 주가' 검색 완료

🔮 > CPU 몇 퍼센트야?
🎯 [check_system] {'info_type': 'cpu'}
CPU 사용률: 23.5%
코어 수: 8개
현재 클럭: 3200 MHz
```

## 📁 프로젝트 구조

```
nexus_shell/
├── main.py              # 진입점 (CLI)
├── config.py            # 설정 (앱 별칭, API 키 등)
├── core/
│   ├── brain.py         # LLM 의도 파악 엔진
│   ├── executor.py      # 시스템 명령 실행기
│   └── functions.py     # Function Calling 정의
├── utils/
│   └── system_info.py   # 시스템 정보 조회
├── .env                 # API 키 (gitignore 대상)
└── requirements.txt
```

## ⚙️ 앱 별칭 추가

`config.py`의 `APP_ALIASES`에 원하는 프로그램을 추가할 수 있습니다:

```python
APP_ALIASES = {
    "카카오톡": r"C:\Program Files (x86)\Kakao\KakaoTalk\KakaoTalk.exe",
    "디스코드": r"C:\Users\사용자명\AppData\Local\Discord\app-1.0.xxx\Discord.exe",
    # ...
}
```

## 📌 현재 지원 명령

| 명령 유형 | 예시 |
|-----------|------|
| 앱 실행 | "크롬 켜줘", "메모장 열어", "계산기 실행" |
| 웹 검색 | "엔비디아 주가 검색", "날씨 알려줘" |
| 사이트 열기 | "유튜브 열어", "네이버 열어" |
| 시스템 정보 | "CPU 사용률", "배터리 확인", "메모리 상태" |
