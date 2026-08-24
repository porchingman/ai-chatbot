from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "dev"
    PORT: int = 8000
    
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    GEMINI_API_KEY: str

    # 학습용 원본 파일이 저장될 루트 경로 (실제 저장 위치: {UPLOAD_ROOT}/{company_code}/{file_name})
    UPLOAD_ROOT: str = "user"

    # ===== RAG 검색(match_knowledge) 튜닝 값 =====
    RAG_CANDIDATE_COUNT: int = 12     # 1차로 넉넉히 가져올 청크 후보 개수 (사례 단위 그룹핑을 위해 기존 4보다 넉넉하게)
    RAG_MATCH_THRESHOLD: float = 0.4  # 코사인 유사도 최소 임계값
    RAG_TOP_CASES: int = 2            # 답변에 참고 사례로 첨부할 최대 게시글(board) 개수
    RAG_CASE_MIN_SIMILARITY: float = 0.6  # 이 값 이상일 때만 "유사 사례"로 인정해 references에 포함

    # .env 파일을 부모 디렉터리(루트) 기준으로 찾을 수 있도록 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()