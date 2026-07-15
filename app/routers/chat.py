from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/v1/chat", tags=["Chat"])

@router.post("/ask", response_model=ChatResponse, summary="RAG 기반 챗봇 질의응답 및 이력 관리")
async def ask_question(payload: ChatRequest):
    """
    고객사 지식을 실시간 검색(RAG)하고 이전 대화 컨텍스트를 기억하여 유기적인 답변을 생성합니다.
    사용된 모든 토큰 사용량과 대화 로그는 자동으로 데이터베이스에 안전하게 기록됩니다.
    """
    result = await ChatService.process_chat(payload)
    return ChatResponse(
        success=True,
        answer=result["answer"],
        input_token=result["input_token"],
        output_token=result["output_token"],
        total_token=result["total_token"],
        response_time_ms=result["response_time_ms"]
    )
