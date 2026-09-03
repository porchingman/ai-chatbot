from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.dependencies import verify_api_key  # 보안 의존성 추가

router = APIRouter(prefix="/v1/chat", tags=["Chat"])

@router.post("/ask", response_model=ChatResponse, summary="RAG 기반 질의응답 (헤더 보안 적용)")
async def ask_question(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    company_code: int = Depends(verify_api_key) # 👈 헤더 검증 가동 및 자동 code 주입
):
    """
    헤더의 Secret Key 동기화를 통해 보안 터널을 확보하고 관련 지식을 매칭해 답변합니다.
    (기존 방식 - 전체 답변 생성이 끝난 뒤 한 번에 응답. 하위 호환용으로 유지)
    """
    result = await ChatService.process_chat(company_code, payload, background_tasks)
    return ChatResponse(
        success=True,
        answer=result["answer"],
        references=result["references"],
        board_link=result["board_link"],
        inquiry_link=result["inquiry_link"],
        input_token=result["input_token"],
        output_token=result["output_token"],
        total_token=result["total_token"],
        response_time_ms=result["response_time_ms"]
    )


@router.post("/ask/stream", summary="RAG 기반 질의응답 - 실시간 스트리밍(SSE) (헤더 보안 적용)")
async def ask_question_stream(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    company_code: int = Depends(verify_api_key)
):
    """
    [신규 - 속도개선] Gemini가 토큰을 생성하는 대로 즉시 클라이언트에 전달하는 SSE 스트리밍 엔드포인트.

    응답 형식 (text/event-stream):
      event: chunk
      data: {"delta": "생성된 텍스트 조각"}

      event: chunk
      data: {"delta": "..."}

      ... (반복) ...

      event: done
      data: {"references": [...], "board_link": "...", "inquiry_link": "...", "input_token": .., "output_token": .., "total_token": .., "response_time_ms": ..}

    오류 발생 시:
      event: error
      data: {"message": "..."}
    """
    generator = ChatService.process_chat_stream(company_code, payload, background_tasks)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 등 프록시의 응답 버퍼링 방지 (있어야 실시간으로 흘러나감)
        }
    )
