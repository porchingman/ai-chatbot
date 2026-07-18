from fastapi import Header, HTTPException, status
from app.database import get_supabase

async def verify_api_key(
    x_company_id: str = Header(..., description="웹서버 발급 고객사 고유 ID"),
    x_api_key: str = Header(..., description="웹서버 인증용 Secret API KEY")
) -> int:
    """
    [일반 보안 레이어] 일반 Chat, Knowledge API용 헤더 인증.
    검증 성공 시 해당 고객사의 고유 번호(company_code)를 반환합니다.
    """
    supabase = get_supabase()

    company_res = supabase.table("company") \
        .select("code", "status") \
        .eq("company_id", x_company_id) \
        .eq("api_key", x_api_key) \
        .execute()

    if not company_res.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 실패: 유효하지 않은 company_id 또는 api_key 헤더 값입니다."
        )

    company = company_res.data[0] # 데이터 리스트 추출 안전 보정

    if company["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 거부: 사용 승인 대기(ready) 중이거나 정지 및 탈퇴(withdrawal)된 계정입니다."
        )

    return company["code"]


async def verify_super_admin(
    x_company_id: str = Header(..., description="웹서버 최고 관리자 ID"),
    x_api_key: str = Header(..., description="웹서버 최고 관리자 Secret API KEY")
) -> int:
    """
    [신규 추가 - 최고 관리자 전용 레이어] 
    Company CRUD API 전용 헤더 인증 필터.
    x_company_id 값이 반드시 'hiappsoft' 여야만 통과됩니다.
    """
    # 1. 1차적으로 기본적인 ID/KEY 유효성 및 active 상태 검증을 수행합니다.
    company_code = await verify_api_key(x_company_id=x_company_id, x_api_key=x_api_key)
    
    # 2. [핵심 요구사항] 최고 관리자 식별자(hiappsoft) 계정 권한 체크를 엄격하게 수행합니다.
    if x_company_id != "hiappsoft":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="권한 오류: 고객사 관리(Company CRUD) API는 오직 'hiappsoft' 마스터 계정만 호출할 수 있습니다."
        )
        
    return company_code
