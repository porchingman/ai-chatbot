from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "dev"
    PORT: int = 8000
    
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    GEMINI_API_KEY: str

    # 학습용 원본 파일이 저장될 루트 경로 (실제 저장 위치: {UPLOAD_ROOT}/{company_code}/{file_name})
    UPLOAD_ROOT: str = "user"

    # .env 파일을 부모 디렉터리(루트) 기준으로 찾을 수 있도록 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()