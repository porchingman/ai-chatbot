from pydantic import BaseModel, HttpUrl
from typing import Optional

# [3단계 관련] 문서 등록 요청/응답 스키마
class DocumentKnowledgeRequest(BaseModel):
    company_id: str          # 웹서버 master.company_id
    source_type: str         # FILE, URL, TEXT 등
    source_code: str         # 웹서버 attachment.code 등 (원본 문서 식별용)
    source_url: HttpUrl      # 다운로드 가능한 파일의 전체 URL
    title: str               # 문서 제목 또는 파일명

class DocumentKnowledgeResponse(BaseModel):
    success: bool
    message: str
    company_code: int
    knowledge_code: int
    total_chunks: int

# [4단계 관련] 챗봇 질의응답 요청/응답 스키마
class ChatRequest(BaseModel):
    company_id: str          # 웹서버 master.company_id (인증 및 고객사 식별)
    member_code: str         # 대화 주체 식별 (메모리 관리용)
    conversation_id: Optional[str] = None  # 미래 확장용
    question: str            # 유저의 질문 내용
    ip: str                  # 로그용 IP 주소

class ChatResponse(BaseModel):
    success: bool
    answer: str
    input_token: int
    output_token: int
    total_token: int
    response_time_ms: int
