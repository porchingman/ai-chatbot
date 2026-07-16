from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import chat, knowledge  # 라우터 임포트

app = FastAPI(
    title="AI ChatBot SaaS API",
    description="상용 운영이 가능한 AI ChatBot SaaS 파이썬 서버 문서입니다.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 지식 관리 라우터 등록
app.include_router(chat.router)  # 채팅 관련 라우터도 등록 (추가 필요 시)
app.include_router(knowledge.router)

@app.get("/")
def root():
    return {
        "message": "This is AI ChatBot SaaS API Server.",
        "version": "1.0.0",
    }

@app.get("/health", tags=["System"], summary="서버 헬스 체크")
def health_check():
    """
    서버의 구동 상태 및 환경을 확인하는 API입니다.
    """
    return {
        "status": "healthy", 
        "environment": settings.ENV,
        "supabase_connected": bool(settings.SUPABASE_URL)
    }
