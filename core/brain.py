import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from core.functions import TOOLS, SYSTEM_PROMPT


class Brain:
    """사용자의 자연어 입력을 해석하여 실행 가능한 명령으로 변환"""
    
    def __init__(self):
        if OPENAI_API_KEY and OPENAI_API_KEY != "여기에_본인_API_키_입력":
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None
        self.conversation_history = []
    
    def interpret(self, user_input: str) -> dict | None:
        """
        사용자 입력을 해석하여 함수 호출 정보를 반환.
        
        Returns:
            {
                "function": "run_app" | "open_url" | "check_system" | "general_response",
                "arguments": { ... }
            }
            또는 해석 실패 시 None
        """
        if self.client is None:
            return None

        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *self.conversation_history
                ],
                tools=TOOLS,
                tool_choice="required",  # 반드시 함수 호출하도록
            )
            
            message = response.choices[0].message
            
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                # 대화 기록에 assistant 응답 추가
                self.conversation_history.append({
                    "role": "assistant",
                    "content": f"[{function_name}] 실행"
                })
                
                return {
                    "function": function_name,
                    "arguments": arguments
                }
            
            return None
            
        except Exception as e:
            print(f"[오류] LLM 해석 실패: {e}")
            return None
    
    def clear_history(self):
        """대화 기록 초기화"""
        self.conversation_history = []
