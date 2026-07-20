from fastapi import APIRouter, status, Query, Depends
from app.models.schemas import CompanyCreateRequest, CompanyUpdateRequest, CompanyInfoResponse, CompanyCommonResponse, CompanyListResponse
from app.services.company_service import CompanyService
from app.dependencies import verify_super_admin # 👈 신규 슈퍼 어드민 의존성 임포트

router = APIRouter(prefix="/v1/company", tags=["Company Admin"])

@router.post("/create", response_model=CompanyInfoResponse, status_code=status.HTTP_201_CREATED, summary="[마스터 어드민] 신규 기업 발급")
def create_company(
    payload: CompanyCreateRequest,
    admin_code: int = Depends(verify_super_admin) # 👈 슈퍼어드민 헤더 강제 검증
):
    """
    SaaS를 이용할 새로운 기업 고객 정보를 바인딩합니다. 
    헤더에 최고 관리자(hiappsoft)의 식별 정보와 API Key가 동기화되어야만 발급이 실행됩니다.
    """
    return CompanyService.create_company(payload)

@router.get("/list", response_model=CompanyListResponse, summary="[마스터 어드민] 전체 기업 고객 리스트 페이징 조회")
def get_company_list(
    page: int = Query(default=1, ge=1, description="조회할 페이지 번호"),
    limit: int = Query(default=10, ge=1, le=100, description="한 페이지당 보여줄 기업 개수"),
    admin_code: int = Depends(verify_super_admin) # 👈 슈퍼어드민 헤더 강제 검증
):
    """
    최고 관리자 전용 대시보드 목록 API입니다. 가입된 기업 전체 숫자와 트래픽 현황을 일괄 스캔합니다.
    """
    return CompanyService.get_company_list(page=page, limit=limit)

@router.get("/info/{code}", response_model=CompanyInfoResponse, summary="[마스터 어드민] 기업 고유 번호(code) 기준 상세 데이터 조회")
def get_company_info(
    code: int,
    admin_code: int = Depends(verify_super_admin) # 👈 슈퍼어드민 헤더 강제 검증
):
    """
    고유 일련번호(code)를 매핑하여 특정 단일 고객사의 실시간 토큰 스펙을 수집합니다.
    """
    return CompanyService.get_company(code)

@router.put("/update/{code}", response_model=CompanyInfoResponse, summary="[마스터 어드민] 기업 상태 변경 또는 프롬프트/키 개편")
def update_company(
    code: int, 
    payload: CompanyUpdateRequest,
    admin_code: int = Depends(verify_super_admin) # 👈 슈퍼어드민 헤더 강제 검증
):
    """
    고유 번호(code)를 추적하여 해당 회사의 지침 프롬프트를 교체하거나 서비스 승인(active), 사용 대기(ready), 서비스 해지(withdrawal) 상태로 전환합니다.
    """
    return CompanyService.update_company(code, payload)

@router.delete("/delete/{code}", response_model=CompanyCommonResponse, summary="[마스터 어드민] 기업 계정 및 종속된 RAG 데이터 아카이브 영구 삭제")
def delete_company(
    code: int,
    admin_code: int = Depends(verify_super_admin) # 👈 슈퍼어드민 헤더 강제 검증
):
    """
    SaaS 철회(withdrawal) 후 마스터가 기업을 영구 파괴할 때 사용합니다.
    """
    CompanyService.delete_company(code)
    return CompanyCommonResponse(
        success=True,
        message="요청하신 고유 코드의 기업 레코드 및 하위 벡터 지식이 삭제 처리되었습니다.",
        code=code
    )
