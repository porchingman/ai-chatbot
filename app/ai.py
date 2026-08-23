import time
import random
import logging
from google import genai
from google.genai import errors as genai_errors
from app.config import settings

logger = logging.getLogger("ai")

# 차세대 구글 임베딩 및 대화 API 표준을 수용하는 통합 클라이언트 (v1beta 채널 통합)
ai_client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options={'api_version': 'v1beta'}
)

# 상용 서비스 고정 표준 모델명 정의 (v1beta 규격 일치 완벽 패치)
EMBEDDING_MODEL = "gemini-embedding-001"  
CHAT_MODEL = "gemini-2.5-flash"          # 앞의 models/ 접두사를 완전히 제거하여 404 차단

# 일시적으로 재시도하면 해결될 가능성이 높은 HTTP 상태코드
# 503 UNAVAILABLE(과부하), 429 RESOURCE_EXHAUSTED(rate limit), 500 INTERNAL 등
RETRYABLE_STATUS_CODES = {429, 500, 503, 504}


def get_ai_client() -> genai.Client:
    """
    통합 초기화된 최신 Gemini API 클라이언트를 반환합니다.
    """
    return ai_client


def call_gemini_with_retry(fn, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 8.0):
    """
    [신규] Gemini API 호출을 감싸서 503(UNAVAILABLE) 등 일시적 오류 발생 시
    지수 백오프(exponential backoff) + 지터(jitter)로 자동 재시도한다.

    사용 예:
        response = call_gemini_with_retry(
            lambda: ai_client.models.generate_content(...)
        )

    - max_retries=3: 최초 시도 포함 총 4번까지 시도 (재시도 3회)
    - base_delay=1.0, max_delay=8.0: 1초 → 2초 → 4초 (최대 8초) 대기 후 재시도, 매번 약간의 랜덤 지터 추가
    - 재시도 불가능한 오류(예: 400 잘못된 요청, 인증 오류 등)는 즉시 그대로 raise
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except genai_errors.APIError as e:
            status_code = getattr(e, "code", None)
            last_exception = e

            if status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                # 재시도 대상이 아니거나, 마지막 시도까지 실패한 경우 → 그대로 예외 전파
                raise

            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.5)
            logger.warning(
                "[Gemini 재시도] status=%s attempt=%s/%s %s초 대기 후 재시도: %s",
                status_code, attempt + 1, max_retries, round(delay, 2), str(e)
            )
            time.sleep(delay)
        except Exception as e:
            # APIError가 아닌 다른 예외(네트워크 타임아웃 등)는 메시지에 재시도 대상 코드가 있는지만 확인
            last_exception = e
            msg = str(e)
            is_retryable_by_message = any(str(code) in msg for code in RETRYABLE_STATUS_CODES) or "UNAVAILABLE" in msg

            if not is_retryable_by_message or attempt == max_retries:
                raise

            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.5)
            logger.warning(
                "[Gemini 재시도] attempt=%s/%s %s초 대기 후 재시도: %s",
                attempt + 1, max_retries, round(delay, 2), msg
            )
            time.sleep(delay)

    # 이론상 도달하지 않지만 안전장치
    raise last_exception
