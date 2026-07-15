from fastapi import APIRouter, HTTPException
from app.models.schemas import DocumentKnowledgeRequest, DocumentKnowledgeResponse
from app.services.rag_service import RAGService
from app.database import get_supabase

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge"])

@router.post("/register", response_model=DocumentKnowledgeResponse, summary="문서 등록 (구조 분리 버전)")
async def register_document(payload: DocumentKnowledgeRequest):
    """
    웹서버에서 넘겨받은 원본 문서를 마스터(knowledge)와 벡터 상세(knowledge_data) 테이블로 분리 저장합니다.
    """
    result = await RAGService.process_and_save_document(payload)
    return DocumentKnowledgeResponse(
        success=True,
        message="마스터 및 텍스트 분할 청킹 임베딩 구조화 저장이 정상 완료되었습니다.",
        company_code=result["company_code"],
        knowledge_code=result["knowledge_code"],
        total_chunks=result["total_chunks"]
    )

@router.delete("/delete", summary="원본 식별자 기준 일괄 삭제")
async def delete_document(company_id: str, source_type: str, source_code: str):
    """
    고객사 코드와 원본 식별 정보를 기준으로 마스터 지식을 지웁니다. 
    Foreign Key 제약 조건에 의해 연관된 모든 벡터 조각 데이터는 원자적으로 자동 제거됩니다.
    """
    supabase = get_supabase()
    
    company_res = supabase.table("company").select("code").eq("company_id", company_id).execute()
    if not company_res.data:
        raise HTTPException(status_code=404, detail="존재하지 않는 company_id 입니다.")
    company_code = company_res.data[0]["code"]
    
    # 마스터 테이블 데이터만 삭제 처리
    res = supabase.table("knowledge").delete()\
        .eq("company_code", company_code)\
        .eq("source_type", source_type)\
        .eq("source_code", source_code).execute()
    
    return {
        "success": True,
        "message": "해당 문서 마스터 및 하위 청크 벡터 데이터 전체가 정상 삭제되었습니다.",
        "deleted_master_count": len(res.data) if res.data else 0
    }
