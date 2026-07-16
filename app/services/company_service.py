from fastapi import HTTPException
from app.database import get_supabase
from app.models.schemas import CompanyCreateRequest, CompanyUpdateRequest

class CompanyService:
    @staticmethod
    def create_company(req: CompanyCreateRequest) -> dict:
        """고객사를 새로 등록합니다. status 값을 외부(POST)로부터 주입받아서 처리합니다."""
        supabase = get_supabase()
        
        # 1. 중복 체크 (company_id)
        exists = supabase.table("company").select("code").eq("company_id", req.company_id).execute()
        if exists.data:
            raise HTTPException(status_code=400, detail="이미 존재하는 company_id 입니다.")
            
        # 2. 중복 체크 (api_key)
        exists_key = supabase.table("company").select("code").eq("api_key", req.api_key).execute()
        if exists_key.data:
            raise HTTPException(status_code=400, detail="이미 사용 중인 api_key 입니다.")

        # 3. [안전장치] 외부에서 들어온 status 값이 유효한 도메인 범위 내에 있는지 검증
        if req.status not in ["active", "ready", "withdrawal"]:
            raise HTTPException(status_code=400, detail="허용되지 않는 status 값입니다. (active, ready, withdrawal)")

        # 4. [제안해주신 구조 적용] 딕셔너리 빌드
        insert_data = {
            "company_id": req.company_id,
            "api_key": req.api_key,
            "prompt": req.prompt,
            "status": req.status
        }
        
        res = supabase.table("company").insert(insert_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="고객사 등록에 실패했습니다.")
            
        return res.data[0]

    @staticmethod
    def get_company(code: int) -> dict:
        """고유 번호(code)를 기준으로 고객사 상세 정보를 조회합니다."""
        supabase = get_supabase()
        
        res = supabase.table("company").select("*").eq("code", code).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="존재하지 않는 고객사(code)입니다.")
            
        return res.data[0]

    @staticmethod
    def get_company_list(page: int = 1, limit: int = 10) -> dict:
        """전체 고객사 목록을 페이징 처리하여 최신 등록 순으로 조회합니다."""
        supabase = get_supabase()
        
        # 1. 전체 카운트 조회 (PostgreSQL 카운트 최적화 방식)
        count_res = supabase.table("company").select("code", count="exact").execute()
        total_count = count_res.count if count_res.count is not None else 0
        
        # 2. 페이징 오프셋 계산 및 벌크 데이터 로드
        start = (page - 1) * limit
        end = start + limit - 1
        
        list_res = supabase.table("company") \
            .select("*") \
            .order("code", desc=True) \
            .range(start, end) \
            .execute()
            
        return {
            "success": True,
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "data": list_res.data if list_res.data else []
        }

    @staticmethod
    def update_company(code: int, req: CompanyUpdateRequest) -> dict:
        """
        고유 번호(code)를 기준으로 회사 정보를 수정합니다.
        company_id 또는 api_key 변경 시 본인의 기존 값을 제외한 타인과만 중복 체크를 수행합니다.
        """
        supabase = get_supabase()
        
        # 1. 대상 고객사가 실제 존재하는지 선행 조회 및 기존 데이터 확보
        current_res = supabase.table("company").select("*").eq("code", code).execute()
        if not current_res.data:
            raise HTTPException(status_code=404, detail="존재하지 않는 고객사(code)입니다.")
        
        # 2. 업데이트 쿼리에 바인딩할 데이터 배열 빌드
        update_data = {}
        
        # [신규 추가] company_id 변경 및 본인 제외 중복 검증
        if req.company_id is not None:
            # 타 회사 중 새로운 company_id를 이미 선점한 곳이 있는지 검증
            dup_id = supabase.table("company") \
                .select("code") \
                .eq("company_id", req.company_id) \
                .neq("code", code) \
                .execute()
            if dup_id.data:
                raise HTTPException(status_code=400, detail="이미 다른 고객사가 사용 중인 company_id 입니다.")
            update_data["company_id"] = req.company_id

        # [신규 추가] api_key 변경 및 본인 제외 중복 검증
        if req.api_key is not None:
            # 타 회사 중 새로운 api_key를 이미 사용 중인 곳이 있는지 검증
            dup_key = supabase.table("company") \
                .select("code") \
                .eq("api_key", req.api_key) \
                .neq("code", code) \
                .execute()
            if dup_key.data:
                raise HTTPException(status_code=400, detail="이미 다른 고객사가 사용 중인 api_key 입니다.")
            update_data["api_key"] = req.api_key

        # 기존 프롬프트 처리
        if req.prompt is not None:
            update_data["prompt"] = req.prompt
            
        # 기존 상태 제어 및 도메인 유효성 체크
        if req.status is not None:
            if req.status not in ["active", "ready", "withdrawal"]:
                raise HTTPException(status_code=400, detail="허용되지 않는 status 값입니다. (active, ready, withdrawal)")
            update_data["status"] = req.status

        # 3. 변경 파라미터가 아예 없는 예외 감지
        if not update_data:
            raise HTTPException(status_code=400, detail="수정할 변경 데이터가 입력되지 않았습니다.")

        # 4. 안전 검증을 통과한 데이터셋만 트랜잭션 업데이트 수행
        res = supabase.table("company").update(update_data).eq("code", code).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="고객사 정보 수정에 실패했습니다.")

        # [상용 안전장치] 리스트 배열 형태의 응답에서 첫 번째 레코드 JSON 객체만 정확히 반환
        return res.data[0]

    @staticmethod
    def delete_company(code: int) -> bool:
        """[수정] 고유 번호(code) 기준으로 지웁니다. CASCADE 전파로 지식 파편까지 한 번에 영구 삭제됩니다."""
        supabase = get_supabase()
        
        exists = supabase.table("company").select("code").eq("code", code).execute()
        if not exists.data:
            raise HTTPException(status_code=404, detail="존재하지 않는 고객사(code)입니다.")

        supabase.table("company").delete().eq("code", code).execute()
        return True
