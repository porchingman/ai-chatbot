# app/dependencies.py
from fastapi import Header, HTTPException, status
from app.database import get_supabase

async def verify_api_key(
    x_company_id: str = Header(..., description="웹서버 발급 고객사 고유 ID"),
    x_api_key: str = Header(..., description="웹서버 인증용 Secret API KEY")
) -> int:
    """
    [보안 레이어] HTTP 헤더에서 고객사 식별 정보와 키를 추출하여 검증합니다.
    검증 성공 시 해당 고객사의 고유 번호(company_code)를 반환합니다.
    """
    supabase = get_supabase()

    # 1. 헤더 정보를 기반으로 Supabase에서 계정 검증 및 조회
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

    company = company_res.data[0]

    # 2. 설계 원칙: 사용 승인된 'active' 계정 상태일 때만 게이트웨이를 열어줍니다.
    if company["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 거부: 사용 승인 대기(ready) 중이거나 정지 및 탈퇴(withdrawal)된 계정입니다."
        )

    # 3. 비즈니스 로직에서 바로 사용할 수 있도록 고유 일련번호(code) 전달
    return company["code"]
