# GPT Function Calling에 등록할 함수 정의들

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_app",
            "description": "프로그램이나 앱을 실행합니다. 예: 크롬, 메모장, VS Code, 계산기, 탐색기 등",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "실행할 앱 이름 (예: 크롬, 메모장, vscode, 계산기)"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "웹 브라우저에서 URL을 열거나 웹 검색을 수행합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "열 URL (예: https://youtube.com) 또는 빈 문자열"
                    },
                    "search_query": {
                        "type": "string",
                        "description": "검색할 키워드 (예: 엔비디아 주가). URL이 비어있을 때 사용"
                    },
                    "site_name": {
                        "type": "string",
                        "description": "열 사이트 별칭 (예: 유튜브, 네이버, 깃허브). URL이 비어있을 때 사용"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_system",
            "description": "시스템 정보를 조회합니다. CPU, 메모리, 디스크, 배터리, 네트워크 등의 현재 상태를 확인합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["cpu", "memory", "disk", "battery", "network", "all"],
                        "description": "조회할 시스템 정보 종류. all이면 전체 요약."
                    }
                },
                "required": ["info_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "general_response",
            "description": "시스템 명령이 아닌 일반적인 질문이나 대화에 응답합니다. 앱 실행, 웹 검색, 시스템 조회와 관련 없는 입력일 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "사용자에게 전달할 응답 메시지"
                    }
                },
                "required": ["message"]
            }
        }
    }
]

SYSTEM_PROMPT = """너는 Nexus Shell이라는 지능형 PC 제어 비서야.
사용자의 자연어 입력을 해석해서 적절한 함수를 호출해야 해.

규칙:
1. 프로그램 실행 요청 → run_app 호출
2. 웹사이트 열기나 검색 요청 → open_url 호출
3. 시스템 상태 질문 → check_system 호출
4. 위 세 가지에 해당하지 않는 일반 대화 → general_response 호출

중요:
- 검색어(search_query)는 사용자가 말한 그대로 전달해. 절대 임의로 풀어쓰거나 번역하지 마.
  예: "무도" → search_query="무도" (O) / search_query="무한도전" (X)
- 특정 사이트에서 검색할 때는 site_name과 search_query를 함께 전달해.

예시:
- "크롬 켜줘" → run_app(app_name="크롬")
- "엔비디아 주가 검색해줘" → open_url(search_query="엔비디아 주가")
- "유튜브 열어" → open_url(site_name="유튜브")
- "유튜브에 무도 검색" → open_url(site_name="유튜브", search_query="무도")
- "네이버에서 날씨 검색" → open_url(site_name="네이버", search_query="날씨")
- "CPU 몇 퍼센트야?" → check_system(info_type="cpu")
- "배터리 얼마나 남았어?" → check_system(info_type="battery")
- "안녕" → general_response(message="안녕하세요! 무엇을 도와드릴까요?")

항상 정확히 하나의 함수를 호출해. 한국어 입력을 잘 이해해야 해.
"""
