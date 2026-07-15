from google import genai
from app.config import settings

# 차세대 구글 임베딩 및 대화 API 표준을 수용하는 통합 클라이언트 (v1beta 채널 통합)
ai_client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options={'api_version': 'v1beta'}
)

# 상용 서비스 고정 표준 모델명 정의 (v1beta 규격 일치 완벽 패치)
EMBEDDING_MODEL = "gemini-embedding-001"  
CHAT_MODEL = "gemini-2.5-flash"          # 앞의 models/ 접두사를 완전히 제거하여 404 차단

def get_ai_client() -> genai.Client:
    """
    통합 초기화된 최신 Gemini API 클라이언트를 반환합니다.
    """
    return ai_client
