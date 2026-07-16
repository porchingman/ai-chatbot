from fastapi import APIRouter, Depends
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.dependencies import verify_api_key  # 보안 의존성 추가

router = APIRouter(prefix="/v1/chat", tags=["Chat"])

@router.post("/ask", response_model=ChatResponse, summary="RAG 기반 질의응답 (헤더 보안 적용)")
async def ask_question(
    payload: ChatRequest,
    company_code: int = Depends(verify_api_key) # 👈 헤더 검증 가동 및 자동 code 주입
):
    """
    헤더의 Secret Key 동기화를 통해 보안 터널을 확보하고 관련 지식을 매칭해 답변합니다.
    """
    result = await ChatService.process_chat(company_code, payload)
    return ChatResponse(
        success=True,
        answer=result["answer"],
        input_token=result["input_token"],
        output_token=result["output_token"],
        total_token=result["total_token"],
        response_time_ms=result["response_time_ms"]
    )
