from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.models.schemas import DocumentKnowledgeResponse, KnowledgeListResponse, BoardKnowledgeRequest, BoardKnowledgeResponse
from app.services.rag_service import RAGService
from app.dependencies import verify_api_key  # 보안 의존성 추가

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge"])

@router.get("/list", response_model=KnowledgeListResponse, summary="[어드민/SaaS] 기업이 학습시킨 원본 문서 마스터 전체 목록 조회")
async def get_knowledge_list(
    company_code: int = Depends(verify_api_key)
):
    """
    HTTP 헤더 인증 체계를 거쳐 해당 기업 고객이 현재까지 학습 완료한 '원본 문서(knowledge)' 전체 목록을 반환합니다.
    """
    return await RAGService.get_knowledge_list_by_company(company_code)


@router.post("/register", response_model=DocumentKnowledgeResponse, summary="문서 등록 (파일 업로드 방식, 헤더 보안 적용)")
async def register_document(
    file: UploadFile = File(..., description="웹서버(PHP)에서 전달하는 학습용 원본 파일 (PDF, DOCX, XLSX)"),
    title: str = Form(..., description="문서 제목 (파일명 등)"),
    company_code: int = Depends(verify_api_key)  # 헤더 검증 가동 및 자동 code 주입
):
    """
    웹서버에서 파일 업로드가 오면 AI 서버 로컬 경로(/user/{company_code}/파일명.확장자)에
    파일을 저장하고, 해당 파일을 읽어 RAG 임베딩 처리 후 적재합니다.
    """
    result = await RAGService.process_and_save_document(company_code, file, title)
    return DocumentKnowledgeResponse(
        success=True,
        message="파일 저장 및 마스터/텍스트 분할 청킹 임베딩 구조화 저장이 정상 완료되었습니다.",
        company_code=company_code,
        knowledge_code=result["knowledge_code"],
        file_name=result["file_name"],
        orig_name=result["orig_name"],
        total_chunks=result["total_chunks"]
    )

@router.post("/register-board", response_model=BoardKnowledgeResponse, summary="게시판 글 등록/수정 시 학습 (Upsert, 헤더 보안 적용)")
async def register_board_document(
    body: BoardKnowledgeRequest,
    company_code: int = Depends(verify_api_key)
):
    """
    그누보드 게시글(board_category + board_id) 등록/수정 시 웹서버가 호출합니다.
    동일 (company_code, board_category, board_id) 조합의 기존 학습 데이터가 있으면 삭제 후 최신 내용으로 재등록합니다.
    """
    result = await RAGService.register_board_document(
        company_code, body.board_category, body.board_id, body.title, body.content
    )
    return BoardKnowledgeResponse(
        success=True,
        message="게시글 학습(등록/수정)이 정상 완료되었습니다.",
        company_code=company_code,
        knowledge_code=result["knowledge_code"],
        board_category=result["board_category"],
        board_id=result["board_id"],
        total_chunks=result["total_chunks"]
    )


@router.delete("/delete-board/{board_category}/{board_id}", summary="게시판 글 삭제 시 학습 데이터 동기화 삭제 (헤더 보안 적용)")
async def delete_board_document(
    board_category: str,
    board_id: int,
    company_code: int = Depends(verify_api_key)
):
    """
    그누보드 게시글 삭제 시 웹서버가 호출합니다.
    해당 게시글로 학습된 knowledge 마스터/청크 데이터를 삭제합니다. (학습 이력이 없어도 에러 없이 종료)
    """
    return await RAGService.delete_board_document(company_code, board_category, board_id)


@router.get("/download/{code}", summary="knowledge 코드 기준 원본 파일 다운로드 (헤더 보안 적용)")
async def download_document(
    code: int,
    company_code: int = Depends(verify_api_key)
):
    """
    보안 인증된 고객사 소유의 문서(knowledge.code 기준)를 실제 원본 파일명 그대로 다운로드합니다.
    """
    target = await RAGService.get_download_target(company_code, code)
    return FileResponse(
        path=target["full_path"],
        filename=target["orig_name"],   # 다운로드 시 사용자가 업로드했던 원본 파일명 그대로 노출
        media_type="application/octet-stream"
    )


@router.delete("/delete/{code}", summary="knowledge 코드 기준 단건 삭제 (헤더 보안 적용)")
async def delete_document(
    code: int,
    company_code: int = Depends(verify_api_key)  # 헤더 검증 가동
):
    """
    보안 인증된 고객사 내부의 특정 문서(knowledge.code 기준, path parameter)를
    물리 파일과 함께 완전 삭제합니다.
    (knowledge_data 하위 청크는 FK CASCADE로 자동 삭제됩니다)
    """
    return await RAGService.delete_document(company_code, code)
