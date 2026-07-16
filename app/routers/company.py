from fastapi import APIRouter, status, Query
from app.models.schemas import CompanyCreateRequest, CompanyUpdateRequest, CompanyInfoResponse, CompanyCommonResponse, CompanyListResponse
from app.services.company_service import CompanyService

router = APIRouter(prefix="/v1/company", tags=["Company"])

@router.post("/create", response_model=CompanyInfoResponse, status_code=status.HTTP_201_CREATED, summary="[어드민] 신규 기업 발급")
def create_company(payload: CompanyCreateRequest):
    """
    SaaS를 이용할 새로운 기업 고객 정보를 바인딩합니다. 초기 생성 시 status 값은 'ready' 상태입니다.
    """
    return CompanyService.create_company(payload)

@router.get("/list", response_model=CompanyListResponse, summary="[어드민] 전체 기업 고객 리스트 페이징 조회")
def get_company_list(
    page: int = Query(default=1, ge=1, description="조회할 페이지 번호"),
    limit: int = Query(default=10, ge=1, le=100, description="한 페이지당 보여줄 기업 개수")
):
    """
    어드민 대시보드용 목록 API입니다. 가입된 기업 전체 숫자와 각 기업의 실시간 누적 트래픽/토큰 사용 현황 현황을 정렬하여 보여줍니다.
    """
    return CompanyService.get_company_list(page=page, limit=limit)

@router.get("/info/{code}", response_model=CompanyInfoResponse, summary="[어드민] 기업 고유 번호(code) 기준 상세 데이터 조회")
def get_company_info(code: int):
    """
    고유 번호(code)를 매핑하여 단일 고객사의 실시간 정산 토큰 스펙을 수집합니다.
    """
    return CompanyService.get_company(code)

@router.put("/update/{code}", response_model=CompanyInfoResponse, summary="[어드민] 기업 상태 변경 또는 프롬프트 개편")
def update_company(code: int, payload: CompanyUpdateRequest):
    """
    고유 번호(code)를 추적하여 해당 회사의 지침 프롬프트를 교체하거나 서비스 승인(active), 사용 대기(ready), 서비스 해지(withdrawal) 상태로 전환합니다.
    """
    return CompanyService.update_company(code, payload)

@router.delete("/delete/{code}", response_model=CompanyCommonResponse, summary="[어드민] 기업 계정 및 종속된 RAG 데이터 아카이브 영구 삭제")
def delete_company(code: int):
    """
    SaaS 철회(withdrawal) 후 영구 파괴 시 사용합니다. 데이터베이스 외래키 연쇄 규칙에 의거하여 하위 조각이 일괄 소멸됩니다.
    """
    CompanyService.delete_company(code)
    return CompanyCommonResponse(
        success=True,
        message="요청하신 고유 코드의 기업 레코드 및 하위 벡터 지식이 완전 증발 처리되었습니다.",
        code=code
    )
