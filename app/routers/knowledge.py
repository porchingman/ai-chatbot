from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import DocumentKnowledgeRequest, DocumentKnowledgeResponse
from app.services.rag_service import RAGService
from app.dependencies import verify_api_key  # 보안 의존성 추가
from app.database import get_supabase

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge"])

@router.post("/register", response_model=DocumentKnowledgeResponse, summary="문서 등록 (헤더 보안 적용)")
async def register_document(
    payload: DocumentKnowledgeRequest,
    company_code: int = Depends(verify_api_key) # 헤더 검증 가동 및 자동 code 주입
):
    """
    헤더를 통해 인증된 고객사 환경에 새로운 문서를 RAG 임베딩 처리하여 적재합니다.
    """
    result = await RAGService.process_and_save_document(company_code, payload)
    return DocumentKnowledgeResponse(
        success=True,
        message="마스터 및 텍스트 분할 청킹 임베딩 구조화 저장이 정상 완료되었습니다.",
        company_code=company_code,
        knowledge_code=result["knowledge_code"],
        total_chunks=result["total_chunks"]
    )

@router.delete("/delete", summary="원본 식별자 기준 일괄 삭제 (헤더 보안 적용)")
async def delete_document(
    source_type: str, 
    source_code: str,
    company_code: int = Depends(verify_api_key) # 헤더 검증 가동
):
    """
    보안 인증된 고객사 내부의 특정 문서를 영구 완전 일괄 삭제합니다.
    """
    supabase = get_supabase()
    res = supabase.table("knowledge").delete()\
        .eq("company_code", company_code)\
        .eq("source_type", source_type)\
        .eq("source_code", source_code).execute()
    
    return {
        "success": True,
        "message": "해당 문서 마스터 및 하위 청크 벡터 데이터 전체가 정상 삭제되었습니다.",
        "deleted_master_count": len(res.data) if res.data else 0
    }
